"""CLI entry point for the pool table diagramming tool."""

import click

from pooltool.table import TABLES
from pooltool.renderer import TableRenderer


def parse_ball(value: str) -> tuple[int, float, float]:
    """Parse a ball spec like '1:10.5,-20.3' into (number, x, y)."""
    try:
        num_part, coord_part = value.split(":")
        ball_number = int(num_part)
        x_str, y_str = coord_part.split(",")
        return (ball_number, float(x_str), float(y_str))
    except (ValueError, IndexError):
        raise click.BadParameter(
            f"Invalid ball format '{value}'. Use NUMBER:X,Y (e.g. '1:10.5,-20.3')")


def parse_point(value: str) -> tuple[float, float]:
    """Parse a coordinate like '10.5,-20.3' into (x, y)."""
    try:
        x_str, y_str = value.split(",")
        return (float(x_str), float(y_str))
    except (ValueError, IndexError):
        raise click.BadParameter(
            f"Invalid coordinate '{value}'. Use X,Y (e.g. '10.5,-20.3')")


def parse_path(value: str) -> tuple[float, float, float, float]:
    """Parse a path spec like '0,25:10,-10' into (x1, y1, x2, y2)."""
    try:
        start, end = value.split(":")
        x1, y1 = start.split(",")
        x2, y2 = end.split(",")
        return (float(x1), float(y1), float(x2), float(y2))
    except (ValueError, IndexError):
        raise click.BadParameter(
            f"Invalid path format '{value}'. Use X1,Y1:X2,Y2 (e.g. '0,25:10,-10')")


@click.command()
@click.option("--table", "table_size", type=click.Choice(list(TABLES.keys())),
              default="9foot", help="Table size")
@click.option("--output", "-o", default="table.png", help="Output image path")
@click.option("--ppi", default=12.0, help="Pixels per inch (controls image resolution)")
@click.option("--ball", "-b", "balls", multiple=True,
              help="Place a ball: NUMBER:X,Y (0=cue, 1-7=solids, 8=eight, 9-15=stripes)")
@click.option("--ghost", "-g", "ghosts", multiple=True,
              help="Ghost ball (dotted circle): X,Y")
@click.option("--path", "-p", "paths", multiple=True,
              help="Ball path (dotted line with arrow): X1,Y1:X2,Y2")
@click.option("--highlight", "-h", "highlights", multiple=True,
              help="Red highlight circle: X,Y")
@click.option("--interactive", "-i", is_flag=True,
              help="Launch interactive web editor instead of generating an image")
@click.option("--port", default=5555, help="Port for interactive editor (default: 5555)")
def main(table_size: str, output: str, ppi: float,
         balls: tuple[str, ...], ghosts: tuple[str, ...],
         paths: tuple[str, ...], highlights: tuple[str, ...],
         interactive: bool, port: int):
    """Generate a pool table diagram.

    Coordinates are in inches from table center (0,0).
    """
    if interactive:
        from pooltool.interactive import run
        run(table_size=table_size, ppi=max(ppi, 24.0), port=port)
        return

    config = TABLES[table_size]
    renderer = TableRenderer(config, pixels_per_inch=ppi)

    ball_list = [parse_ball(b) for b in balls] if balls else None
    ghost_list = [parse_point(g) for g in ghosts] if ghosts else None
    path_list = [parse_path(p) for p in paths] if paths else None
    highlight_list = [parse_point(h) for h in highlights] if highlights else None

    img = renderer.render(balls=ball_list, ghosts=ghost_list,
                          paths=path_list, highlights=highlight_list)
    img.save(output)
    click.echo(f"Saved {config.name} table diagram to {output}")


if __name__ == "__main__":
    main()
