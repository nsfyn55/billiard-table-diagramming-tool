"""CLI entry point for the pool table diagramming tool."""

import click

from pooltool.table import TABLES
from pooltool.renderer import TableRenderer


@click.command()
@click.option("--table", "table_size", type=click.Choice(list(TABLES.keys())),
              default="9foot", help="Table size")
@click.option("--output", "-o", default="table.png", help="Output image path")
@click.option("--ppi", default=12.0, help="Pixels per inch (controls image resolution)")
def main(table_size: str, output: str, ppi: float):
    """Generate a pool table diagram."""
    config = TABLES[table_size]
    renderer = TableRenderer(config, pixels_per_inch=ppi)
    img = renderer.render()
    img.save(output)
    click.echo(f"Saved {config.name} table diagram to {output}")


if __name__ == "__main__":
    main()
