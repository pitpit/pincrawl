#!/usr/bin/env python3

import click
import logging
from commands.ads import ads
from commands.products import products

# Configure logging globally
logging.basicConfig(
    level=logging.DEBUG,  # Set to DEBUG so all levels can be controlled dynamically
    format='%(levelname)s - %(message)s',
    force=True  # Override any existing configuration
)

@click.group()
@click.option('--verbose', '-v', count=True, help='Increase verbosity (-v for WARNING, -vv for INFO, -vvv for DEBUG)')
@click.version_option(version="0.1.0", prog_name="pincrawl")
def pincrawl(verbose):
    """PinCrawl - A powerful web crawling tool."""

    # Configure logging level based on verbosity
    if verbose == 0 or verbose == 1:
        log_level = logging.WARNING  # Default: show warnings and errors
    elif verbose == 2:
        log_level = logging.INFO     # -vv: show info, warnings, and errors
    else:  # verbose >= 3
        log_level = logging.DEBUG    # -vvv: show everything

    logging.getLogger().setLevel(log_level)


# Add the groups to pincrawl
pincrawl.add_command(ads)
pincrawl.add_command(products)


if __name__ == "__main__":
    pincrawl()
