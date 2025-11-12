#!/usr/bin/env python3

import click
import logging
from pincrawl.commands.ads import ads_crawl, ads_scrape
from pincrawl.commands.watching import watching_send

logger = logging.getLogger(__name__)


@click.command()
def cron():
    """Execute the complete workflow: crawl ads, scrape them, and send notifications."""

    # Step 1: Crawl for new ads
    ctx = click.get_current_context()
    ctx.invoke(ads_crawl)

    # Step 2: Scrape unscraped ads
    ctx.invoke(ads_scrape, limit=None, force=False)

    # Step 3: Send notifications
    ctx.invoke(watching_send)
