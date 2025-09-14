#!/usr/bin/env python3

import click
from commands.ads import ads
from commands.products import products

@click.group()
@click.version_option(version="0.1.0", prog_name="pincrawl")
def pincrawl():
    """PinCrawl - A powerful web crawling tool."""
    pass


# Add the groups to pincrawl
pincrawl.add_command(ads)
pincrawl.add_command(products)


if __name__ == "__main__":
    pincrawl()
