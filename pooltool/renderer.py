"""Renders pool table diagrams to PNG images using Pillow."""

import math
from PIL import Image, ImageDraw

from pooltool.table import TableConfig


# Colors
FELT_GREEN = (0, 100, 0)
RAIL_BROWN = (101, 67, 33)
POCKET_BLACK = (20, 20, 20)
CUSHION_GREEN = (34, 139, 34)


class TableRenderer:
    """Renders a pool table to an image."""

    def __init__(self, config: TableConfig, pixels_per_inch: float = 12.0):
        self.config = config
        self.ppi = pixels_per_inch

        # Margin around the playing surface for the rail border
        self.rail_width = 4.0  # inches of visible rail around the felt
        self.margin = 1.0  # inches of empty space outside rail

        # Total image size in inches then pixels
        total_width_in = config.playing_surface_width + 2 * (self.rail_width + self.margin)
        total_height_in = config.playing_surface_length + 2 * (self.rail_width + self.margin)
        self.img_w = int(total_width_in * self.ppi)
        self.img_h = int(total_height_in * self.ppi)

        # Offset from image origin to the top-left corner of the playing surface
        self.offset_x = (self.rail_width + self.margin) * self.ppi
        self.offset_y = (self.rail_width + self.margin) * self.ppi

    def table_to_pixel(self, x: float, y: float) -> tuple[float, float]:
        """Convert table coordinates (0,0 = center) to pixel coordinates.

        Table y-axis points up, pixel y-axis points down.
        """
        px = self.offset_x + (x + self.config.half_width) * self.ppi
        py = self.offset_y + (self.config.half_length - y) * self.ppi
        return px, py

    def render(self) -> Image.Image:
        """Render the table and return a PIL Image."""
        img = Image.new("RGB", (self.img_w, self.img_h), RAIL_BROWN)
        draw = ImageDraw.Draw(img)

        self._draw_felt(draw)
        self._draw_pockets(draw)
        self._draw_cushions(draw)
        self._draw_pocket_rail_covers(draw)

        return img

    def _draw_felt(self, draw: ImageDraw.Draw):
        """Draw the green playing surface."""
        x0, y0 = self.table_to_pixel(-self.config.half_width, self.config.half_length)
        x1, y1 = self.table_to_pixel(self.config.half_width, -self.config.half_length)
        draw.rectangle([x0, y0, x1, y1], fill=FELT_GREEN)

    def _draw_pocket_rail_covers(self, draw: ImageDraw.Draw):
        """Draw brown rectangles flanking each side pocket to define the opening width."""
        cfg = self.config
        hw = cfg.half_width
        cw = cfg.cushion_width
        spr = cfg.side_pocket_width / 2
        taper = cw * 0.5
        # How wide the visible pocket opening is (half-width from center)
        opening_half = spr - taper  # flush with cushion points cutting into pocket
        cover_extent = spr + 2.0   # how far the cover extends beyond the pocket

        for side_x, rail_outer_x in [(-hw, -hw - self.rail_width - 1),
                                      (hw, hw + self.rail_width + 1)]:
            # Upper flank
            x0, y0 = self.table_to_pixel(min(side_x, rail_outer_x), cover_extent)
            x1, y1 = self.table_to_pixel(max(side_x, rail_outer_x), opening_half)
            draw.rectangle([x0, y0, x1, y1], fill=RAIL_BROWN)

            # Lower flank
            x0, y0 = self.table_to_pixel(min(side_x, rail_outer_x), -opening_half)
            x1, y1 = self.table_to_pixel(max(side_x, rail_outer_x), -cover_extent)
            draw.rectangle([x0, y0, x1, y1], fill=RAIL_BROWN)

    def _draw_cushions(self, draw: ImageDraw.Draw):
        """Draw the 6 cushion segments with triangular endpoints near pockets."""
        cfg = self.config
        hw = cfg.half_width
        hl = cfg.half_length
        cw = cfg.cushion_width
        # How far from the corner/side pocket center the cushion starts
        corner_gap = cfg.corner_pocket_width / 2 - 1.0  # overlap into corner pocket
        # side_gap: where the rail edge ends near the pocket
        # taper: how far back from rail_end the inner tip sits
        # tip lands at side_gap + taper, so set side_gap = spr - taper for tip at pocket edge
        spr = cfg.side_pocket_width / 2
        taper = cw * 0.5
        side_gap = spr - taper  # taper tip lands right at the pocket edge

        # Top rail: one segment across the top, between the two corner pockets
        # Runs from left corner pocket to right corner pocket
        self._draw_cushion_segment(draw,
            rail_start=(-hw + corner_gap, hl),  # left end (near left corner pocket)
            rail_end=(hw - corner_gap, hl),      # right end (near right corner pocket)
            inward_direction=(0, -1),             # cushion extends downward (into table)
            cushion_width=cw, taper=taper)

        # Bottom rail: one segment across the bottom
        self._draw_cushion_segment(draw,
            rail_start=(-hw + corner_gap, -hl),
            rail_end=(hw - corner_gap, -hl),
            inward_direction=(0, 1),
            cushion_width=cw, taper=taper)

        # Left rail top half: from top-left corner pocket down to left side pocket
        self._draw_cushion_segment(draw,
            rail_start=(-hw, hl - corner_gap),
            rail_end=(-hw, side_gap),
            inward_direction=(1, 0),
            cushion_width=cw, taper=taper)

        # Left rail bottom half: from left side pocket down to bottom-left corner pocket
        self._draw_cushion_segment(draw,
            rail_start=(-hw, -side_gap),
            rail_end=(-hw, -hl + corner_gap),
            inward_direction=(1, 0),
            cushion_width=cw, taper=taper)

        # Right rail top half
        self._draw_cushion_segment(draw,
            rail_start=(hw, hl - corner_gap),
            rail_end=(hw, side_gap),
            inward_direction=(-1, 0),
            cushion_width=cw, taper=taper)

        # Right rail bottom half
        self._draw_cushion_segment(draw,
            rail_start=(hw, -side_gap),
            rail_end=(hw, -hl + corner_gap),
            inward_direction=(-1, 0),
            cushion_width=cw, taper=taper)

    def _draw_cushion_segment(self, draw: ImageDraw.Draw,
                               rail_start: tuple[float, float],
                               rail_end: tuple[float, float],
                               inward_direction: tuple[float, float],
                               cushion_width: float, taper: float):
        """Draw a single cushion segment as a polygon with tapered triangle ends.

        The cushion runs along the rail from rail_start to rail_end.
        It extends inward by cushion_width. The ends taper to a point
        over the length of `taper` inches.

        The shape is: triangle point at start -> full width body -> triangle point at end
        """
        dx = inward_direction[0]
        dy = inward_direction[1]

        # Direction along the rail (from start to end)
        rail_dx = rail_end[0] - rail_start[0]
        rail_dy = rail_end[1] - rail_start[1]
        rail_len = math.sqrt(rail_dx**2 + rail_dy**2)
        rdx = rail_dx / rail_len  # unit vector along rail
        rdy = rail_dy / rail_len

        # Points along the rail edge (outer edge)
        rs = rail_start
        re = rail_end

        # Points along the inner edge (shifted inward by cushion_width)
        # But tapered at the ends
        # Start taper point (triangle tip) — on the inner edge at start
        start_tip = (rs[0] + dx * cushion_width + rdx * taper,
                     rs[1] + dy * cushion_width + rdy * taper)
        # End taper point (triangle tip) — on the inner edge at end
        end_tip = (re[0] + dx * cushion_width - rdx * taper,
                   re[1] + dy * cushion_width - rdy * taper)

        # Full polygon: rail_start -> start_tip (inner) -> end_tip (inner) -> rail_end
        points = [
            self.table_to_pixel(*rs),
            self.table_to_pixel(*start_tip),
            self.table_to_pixel(*end_tip),
            self.table_to_pixel(*re),
        ]

        draw.polygon(points, fill=CUSHION_GREEN)

    def _draw_pockets(self, draw: ImageDraw.Draw):
        """Draw all six pockets."""
        cfg = self.config
        hw = cfg.half_width
        hl = cfg.half_length
        cpr = cfg.corner_pocket_width      # corner pocket radius (full width)
        spr = cfg.side_pocket_width / 2    # side pocket radius

        # Corner pockets - U-shapes at 45° angles
        # rotation_deg: 0=opens down in pixel space (up on table)
        corner_offset = cpr / 2 * 0.3
        corners = [
            (-hw - corner_offset, -hl - corner_offset, 225),   # bottom-left: opens toward top-right
            (hw + corner_offset, -hl - corner_offset, 315),    # bottom-right: opens toward top-left
            (hw + corner_offset, hl + corner_offset, 45),      # top-right: opens toward bottom-left
            (-hw - corner_offset, hl + corner_offset, 135),    # top-left: opens toward bottom-right
        ]
        for cx, cy, rot in corners:
            self._draw_corner_pocket(draw, cx, cy, cpr / 2, rot)

        # Side pockets - stadium shape (semicircle + short rect + mirrored semicircle)
        cw = cfg.cushion_width
        self._draw_side_pocket_stadium(draw, -hw + cw - spr, 0, spr, 270)
        self._draw_side_pocket_stadium(draw, hw - cw + spr, 0, spr, 90)

    def _draw_corner_pocket(self, draw: ImageDraw.Draw, table_x: float, table_y: float,
                            radius: float, rotation_deg: float):
        """Draw a corner pocket as a U-shape: semicircle + rectangular walls.

        The U opens upward (toward positive y in pixel space) by default,
        then is rotated by rotation_deg around the center point.

        radius: half-width of the U
        rotation_deg: rotation in degrees (0 = opening faces up in pixel coords)
        """
        px, py = self.table_to_pixel(table_x, table_y)
        r_px = radius * self.ppi
        wall_length = r_px * 1.0  # how tall the straight walls are

        # Build U-shape points: opening at top, curve at bottom
        # Left wall top -> left wall bottom -> arc across bottom -> right wall bottom -> right wall top
        num_arc_points = 30
        points = []

        # Top-left (opening)
        points.append((-r_px, -wall_length))
        # Bottom-left (where arc starts)
        points.append((-r_px, 0))

        # Semicircle arc from left to right across the bottom (180° to 0°)
        for i in range(num_arc_points + 1):
            angle = math.pi - (math.pi * i / num_arc_points)  # pi -> 0
            ax = r_px * math.cos(angle)
            ay = r_px * math.sin(angle)  # positive = up, but we want curve going down
            points.append((ax, ay))

        # Bottom-right to top-right
        points.append((r_px, 0))
        points.append((r_px, -wall_length))

        # Rotate all points
        rot_rad = math.radians(rotation_deg)
        cos_r = math.cos(rot_rad)
        sin_r = math.sin(rot_rad)

        rotated = []
        for x, y in points:
            rx = x * cos_r - y * sin_r
            ry = x * sin_r + y * cos_r
            rotated.append((px + rx, py + ry))

        draw.polygon(rotated, fill=POCKET_BLACK)

    def _draw_side_pocket_stadium(self, draw: ImageDraw.Draw, table_x: float, table_y: float,
                                   radius: float, rotation_deg: float):
        """Draw a side pocket as a stadium: semicircle + short rect + mirrored semicircle.

        Same center/radius/rotation as the U-shape, but with a second semicircle
        at the open end and a squished rectangle between them.
        """
        px, py = self.table_to_pixel(table_x, table_y)
        r_px = radius * self.ppi
        outer_r_px = r_px * 0.7  # outer semicircle (back of pocket)
        rect_height = r_px * 0.1   # short rectangle between the two semicircles
        num_arc_points = 30
        points = []

        # Inner semicircle (felt side, same width as pocket opening) — at y=0
        for i in range(num_arc_points + 1):
            angle = math.pi - (math.pi * i / num_arc_points)  # pi -> 0
            ax = r_px * math.cos(angle)
            ay = r_px * math.sin(angle)
            points.append((ax, ay))

        # Right wall going up to the outer semicircle
        points.append((r_px, -rect_height))

        # Outer semicircle (rail side, smaller) — at y=-rect_height
        for i in range(num_arc_points + 1):
            angle = -(math.pi * i / num_arc_points)  # 0 -> -pi
            # Same width (r_px) at the connection, but the curve is shallower
            ax = r_px * math.cos(angle)
            ay = -rect_height + outer_r_px * math.sin(angle)
            points.append((ax, ay))

        # Left wall going back down
        points.append((-r_px, 0))

        # Rotate all points
        rot_rad = math.radians(rotation_deg)
        cos_r = math.cos(rot_rad)
        sin_r = math.sin(rot_rad)

        rotated = []
        for x, y in points:
            rx = x * cos_r - y * sin_r
            ry = x * sin_r + y * cos_r
            rotated.append((px + rx, py + ry))

        draw.polygon(rotated, fill=POCKET_BLACK)
