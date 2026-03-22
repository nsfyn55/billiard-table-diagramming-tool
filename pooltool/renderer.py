"""Renders pool table diagrams to PNG images using Pillow."""

import math
from PIL import Image, ImageDraw

from pooltool.table import TableConfig


# Colors
FELT_GREEN = (0, 100, 0)
RAIL_BROWN = (101, 67, 33)
POCKET_BLACK = (20, 20, 20)
CUSHION_GREEN = (34, 139, 34)
DIAMOND_WHITE = (220, 200, 160)


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
        self._draw_spots(draw)
        self._draw_debug_ball(draw)

        # Pockets first
        self._draw_side_pockets(draw)
        self._draw_corner_pockets(draw)

        # Covers on top of pockets
        self._draw_side_pocket_covers(draw)
        self._draw_corner_pocket_covers(draw)

        # Cushions last, on top of everything
        self._draw_side_cushions(draw)
        self._draw_corner_cushions(draw)

        # Diamonds on top of rails
        self._draw_diamonds(draw)

        return img

    def _draw_felt(self, draw: ImageDraw.Draw):
        """Draw the green playing surface."""
        x0, y0 = self.table_to_pixel(-self.config.half_width, self.config.half_length)
        x1, y1 = self.table_to_pixel(self.config.half_width, -self.config.half_length)
        draw.rectangle([x0, y0, x1, y1], fill=FELT_GREEN)

    def _draw_spots(self, draw: ImageDraw.Draw):
        """Draw the foot spot and head spot with gradient shading."""
        cfg = self.config
        hl = cfg.half_length

        # Spots at 1/4 length from each end
        foot_spot = (0, -hl / 2)
        head_spot = (0, hl / 2)

        spot_radius = 0.5  # inches (1-inch diameter spot)

        for sx, sy in [foot_spot, head_spot]:
            px, py = self.table_to_pixel(sx, sy)
            r_outer = spot_radius * self.ppi
            r_body = r_outer * 0.7
            r_center = r_outer * 0.25

            # Outer border ring
            draw.ellipse(
                [px - r_outer, py - r_outer, px + r_outer, py + r_outer],
                fill=(60, 60, 60))
            # Main body
            draw.ellipse(
                [px - r_body, py - r_body, px + r_body, py + r_body],
                fill=(120, 120, 120))
            # Center point
            draw.ellipse(
                [px - r_center, py - r_center, px + r_center, py + r_center],
                fill=(20, 20, 20))

    def _draw_debug_ball(self, draw: ImageDraw.Draw):
        """Draw a single ball at the foot spot for scale reference."""
        cfg = self.config
        px, py = self.table_to_pixel(0, -cfg.half_length / 2)
        r = cfg.ball_radius * self.ppi
        draw.ellipse([px - r, py - r, px + r, py + r], fill=(255, 255, 255))
        # Slight shadow/outline
        draw.ellipse([px - r, py - r, px + r, py + r], outline=(180, 180, 180))

    # ========================================================================
    # SIDE POCKETS — fully self-contained, do not modify for corner work
    # ========================================================================

    def _draw_side_pocket_covers(self, draw: ImageDraw.Draw):
        """Draw brown rectangles flanking each side pocket to define the opening width."""
        cfg = self.config
        hw = cfg.half_width
        cw = cfg.cushion_width
        spr = cfg.side_pocket_width / 2
        taper = cw * 0.5 / 1.33
        opening_half = spr - taper
        cover_extent = spr + 2.0

        for side_x, rail_outer_x in [(-hw, -hw - self.rail_width - 1),
                                      (hw, hw + self.rail_width + 1)]:
            x0, y0 = self.table_to_pixel(min(side_x, rail_outer_x), cover_extent)
            x1, y1 = self.table_to_pixel(max(side_x, rail_outer_x), opening_half)
            draw.rectangle([x0, y0, x1, y1], fill=RAIL_BROWN)

            x0, y0 = self.table_to_pixel(min(side_x, rail_outer_x), -opening_half)
            x1, y1 = self.table_to_pixel(max(side_x, rail_outer_x), -cover_extent)
            draw.rectangle([x0, y0, x1, y1], fill=RAIL_BROWN)

    def _draw_side_pockets(self, draw: ImageDraw.Draw):
        """Draw the two side pockets as stadium shapes."""
        cfg = self.config
        hw = cfg.half_width
        cw = cfg.cushion_width
        spr = cfg.side_pocket_width / 2
        self._draw_side_pocket_stadium(draw, -hw + cw - spr, 0, spr, 270)
        self._draw_side_pocket_stadium(draw, hw - cw + spr, 0, spr, 90)

    def _draw_side_cushions(self, draw: ImageDraw.Draw):
        """Draw the 4 cushion segments along the long rails (split by side pockets)."""
        cfg = self.config
        hw = cfg.half_width
        hl = cfg.half_length
        cw = cfg.cushion_width
        corner_gap = cfg.corner_pocket_width * 0.55
        spr = cfg.side_pocket_width / 2
        taper = cw * 0.5 / 1.33
        corner_taper = cw
        side_gap = spr - taper

        # Left rail top half (start near corner, end near side pocket)
        self._draw_cushion_segment(draw,
            rail_start=(-hw, hl - corner_gap),
            rail_end=(-hw, side_gap),
            inward_direction=(1, 0),
            cushion_width=cw, taper=taper, start_taper=corner_taper)

        # Left rail bottom half (start near side pocket, end near corner)
        self._draw_cushion_segment(draw,
            rail_start=(-hw, -side_gap),
            rail_end=(-hw, -hl + corner_gap),
            inward_direction=(1, 0),
            cushion_width=cw, taper=taper, end_taper=corner_taper)

        # Right rail top half (start near corner, end near side pocket)
        self._draw_cushion_segment(draw,
            rail_start=(hw, hl - corner_gap),
            rail_end=(hw, side_gap),
            inward_direction=(-1, 0),
            cushion_width=cw, taper=taper, start_taper=corner_taper)

        # Right rail bottom half (start near side pocket, end near corner)
        self._draw_cushion_segment(draw,
            rail_start=(hw, -side_gap),
            rail_end=(hw, -hl + corner_gap),
            inward_direction=(-1, 0),
            cushion_width=cw, taper=taper, end_taper=corner_taper)

    # ========================================================================
    # CORNER POCKETS
    # ========================================================================

    def _draw_corner_pockets(self, draw: ImageDraw.Draw):
        """Draw the four corner pockets as stadium shapes at 45° angles.

        Same shape as side pockets, oriented so the elongation axis bisects
        the 90° corner into two 45° angles. Positioned at the corner point.
        """
        cfg = self.config
        hw = cfg.half_width
        hl = cfg.half_length
        cpr = cfg.corner_pocket_width / 2  # pocket radius

        # Shift pocket center along 45° bisection toward playing surface
        inset = cpr * 0.55
        d = inset / math.sqrt(2)  # x and y components of 45° shift
        corners = [
            (-hw + d, -hl + d, 225),   # bottom-left
            (hw - d, -hl + d, 315),    # bottom-right
            (hw - d, hl - d, 45),      # top-right
            (-hw + d, hl - d, 135),    # top-left
        ]
        for cx, cy, rot in corners:
            self._draw_side_pocket_stadium(draw, cx, cy, cpr, rot)

    def _draw_corner_pocket_covers(self, draw: ImageDraw.Draw):
        """Draw rotated rectangles flanking each corner pocket opening.

        Positioned flush with the cushion taper points at each corner.
        """
        cfg = self.config
        hw = cfg.half_width
        hl = cfg.half_length
        cpr = cfg.corner_pocket_width / 2
        corner_gap = cfg.corner_pocket_width * 0.55
        inset = cpr * 0.55
        d = inset / math.sqrt(2)

        # Perpendicular distance from pocket center to cushion endpoint
        perp_dist = corner_gap / math.sqrt(2)

        corners = [
            (-hw + d, -hl + d, 225),
            (hw - d, -hl + d, 315),
            (hw - d, hl - d, 45),
            (-hw + d, hl - d, 135),
        ]
        for cx, cy, rot in corners:
            self._draw_rotated_flank(draw, cx, cy, cpr, rot, perp_dist)

    def _draw_rotated_flank(self, draw: ImageDraw.Draw, cx: float, cy: float,
                             pocket_radius: float, rotation_deg: float,
                             perp_dist: float):
        """Draw two rotated flanking rectangles on either side of a corner pocket opening."""
        px, py = self.table_to_pixel(cx, cy)
        r_px = pocket_radius * self.ppi
        perp_dist_px = perp_dist * self.ppi
        rot_rad = math.radians(rotation_deg)
        cos_r = math.cos(rot_rad)
        sin_r = math.sin(rot_rad)

        flank_length = r_px * 2.0
        flank_width = r_px * 0.5

        for side in [-1, 1]:
            # Inner edge flush with cushion taper point, extending outward
            perp_offset = side * (perp_dist_px + flank_width / 2)

            hw_local = flank_width / 2
            hh_local = flank_length / 2
            rect_points = [
                (perp_offset - hw_local, -hh_local),
                (perp_offset + hw_local, -hh_local),
                (perp_offset + hw_local, hh_local),
                (perp_offset - hw_local, hh_local),
            ]

            rotated = []
            for x, y in rect_points:
                rx = x * cos_r - y * sin_r
                ry = x * sin_r + y * cos_r
                rotated.append((px + rx, py + ry))

            draw.polygon(rotated, fill=RAIL_BROWN)

    def _draw_corner_cushions(self, draw: ImageDraw.Draw):
        """Draw the 2 cushion segments along the short rails (top and bottom)."""
        cfg = self.config
        hw = cfg.half_width
        hl = cfg.half_length
        cw = cfg.cushion_width
        corner_gap = cfg.corner_pocket_width * 0.55
        taper = cw * 0.5
        corner_taper = cw

        # Top rail (both ends near corners)
        self._draw_cushion_segment(draw,
            rail_start=(-hw + corner_gap, hl),
            rail_end=(hw - corner_gap, hl),
            inward_direction=(0, -1),
            cushion_width=cw, taper=taper, start_taper=corner_taper, end_taper=corner_taper)

        # Bottom rail (both ends near corners)
        self._draw_cushion_segment(draw,
            rail_start=(-hw + corner_gap, -hl),
            rail_end=(hw - corner_gap, -hl),
            inward_direction=(0, 1),
            cushion_width=cw, taper=taper, start_taper=corner_taper, end_taper=corner_taper)

    def _draw_diamonds(self, draw: ImageDraw.Draw):
        """Draw diamond sights on the rails."""
        cfg = self.config
        hw = cfg.half_width
        hl = cfg.half_length
        cw = cfg.cushion_width

        # Diamond spacing: length/8 along long rails, width/4 along short rails
        # These are equal on standard tables (length = 2 * width)
        long_spacing = cfg.playing_surface_length / 8
        short_spacing = cfg.playing_surface_width / 4

        # Diamond position on the rail: halfway between outer table edge and cushion edge
        rail_center = self.rail_width / 2
        diamond_size = 0.4  # inches, half-width of the diamond shape

        # Long rails: 3 diamonds on each side of the side pocket (skip i=4, that's the pocket)
        for i in range(1, 8):
            if i == 4:  # side pocket position
                continue
            y = -hl + i * long_spacing
            for sign in [-1, 1]:
                x = sign * (hw + rail_center)
                self._draw_diamond(draw, x, y, diamond_size)

        # Short rails: 3 diamonds on each
        for i in range(1, 4):
            x = -hw + i * short_spacing
            for sign in [-1, 1]:
                y = sign * (hl + rail_center)
                self._draw_diamond(draw, x, y, diamond_size)

    def _draw_diamond(self, draw: ImageDraw.Draw, table_x: float, table_y: float,
                       size: float):
        """Draw a single diamond shape (rotated square) at the given table position."""
        px, py = self.table_to_pixel(table_x, table_y)
        s = size * self.ppi
        points = [
            (px, py - s),   # top
            (px + s, py),   # right
            (px, py + s),   # bottom
            (px - s, py),   # left
        ]
        draw.polygon(points, fill=DIAMOND_WHITE)

    def _draw_cushion_segment(self, draw: ImageDraw.Draw,
                               rail_start: tuple[float, float],
                               rail_end: tuple[float, float],
                               inward_direction: tuple[float, float],
                               cushion_width: float, taper: float,
                               start_taper: float | None = None,
                               end_taper: float | None = None):
        """Draw a single cushion segment as a polygon with tapered triangle ends.

        The cushion runs along the rail from rail_start to rail_end.
        It extends inward by cushion_width. The ends taper to a point.
        start_taper/end_taper override taper at each end independently.
        """
        if start_taper is None:
            start_taper = taper
        if end_taper is None:
            end_taper = taper

        dx = inward_direction[0]
        dy = inward_direction[1]

        # Direction along the rail (from start to end)
        rail_dx = rail_end[0] - rail_start[0]
        rail_dy = rail_end[1] - rail_start[1]
        rail_len = math.sqrt(rail_dx**2 + rail_dy**2)
        rdx = rail_dx / rail_len  # unit vector along rail
        rdy = rail_dy / rail_len

        rs = rail_start
        re = rail_end

        start_tip = (rs[0] + dx * cushion_width + rdx * start_taper,
                     rs[1] + dy * cushion_width + rdy * start_taper)
        end_tip = (re[0] + dx * cushion_width - rdx * end_taper,
                   re[1] + dy * cushion_width - rdy * end_taper)

        points = [
            self.table_to_pixel(*rs),
            self.table_to_pixel(*start_tip),
            self.table_to_pixel(*end_tip),
            self.table_to_pixel(*re),
        ]

        draw.polygon(points, fill=CUSHION_GREEN)

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
