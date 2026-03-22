"""Table configuration and dimensions for standard pool tables."""

from dataclasses import dataclass


@dataclass
class TableConfig:
    """Real-world pool table dimensions in inches."""
    name: str
    playing_surface_width: float   # short axis (x)
    playing_surface_length: float  # long axis (y)
    ball_diameter: float
    corner_pocket_width: float
    side_pocket_width: float
    cushion_width: float           # how far the cushion nose extends over the felt

    @property
    def ball_radius(self) -> float:
        return self.ball_diameter / 2

    @property
    def half_width(self) -> float:
        return self.playing_surface_width / 2

    @property
    def half_length(self) -> float:
        return self.playing_surface_length / 2

    @property
    def max_ball_x(self) -> float:
        return self.half_width - self.ball_radius

    @property
    def max_ball_y(self) -> float:
        return self.half_length - self.ball_radius


TABLES = {
    "7foot": TableConfig(
        name="7-foot",
        playing_surface_width=39.0,
        playing_surface_length=78.0,
        ball_diameter=2.25,
        corner_pocket_width=4.95,
        side_pocket_width=5.0,
        cushion_width=2.0,
    ),
    "8foot": TableConfig(
        name="8-foot",
        playing_surface_width=44.0,
        playing_surface_length=88.0,
        ball_diameter=2.25,
        corner_pocket_width=5.225,
        side_pocket_width=5.25,
        cushion_width=2.0,
    ),
    "9foot": TableConfig(
        name="9-foot",
        playing_surface_width=50.0,
        playing_surface_length=100.0,
        ball_diameter=2.25,
        corner_pocket_width=5.5,
        side_pocket_width=5.5,
        cushion_width=2.0,
    ),
}
