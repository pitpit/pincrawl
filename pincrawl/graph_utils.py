#!/usr/bin/env python3
"""Utilities for generating price timeline graphs for pinball machines."""

import os
from typing import List, Tuple, Optional
from datetime import datetime, timedelta
import matplotlib
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from matplotlib.ticker import FixedLocator


def generate_price_graph(dates: List[datetime], prices: List[float], output_path: str, no_data: bool = False, format: str = 'svg', ad_chains: List[Tuple[int, bool]] = None) -> str:
    """Generate a price timeline graph and save it to disk.

    Args:
        dates: List of datetime objects for the x-axis
        prices: List of prices (in euros) for the y-axis
        output_path: Full path where the graph should be saved
        no_data: If True and no data, show "No data" text in center
        format: Output format ('svg' or 'png')
        ad_chains: List of tuples (index, is_end_of_chain) indicating which ads are end of chain

    Raises:
        Exception: If graph generation fails
    """
    matplotlib.use('Agg')  # Use non-interactive backend

    # Create output directory if it doesn't exist
    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    # Create figure with specific size (320px wide x 120px high at 100 DPI)
    fig, ax = plt.subplots(figsize=(3.2, 1.2), dpi=100)

    # Plot the data (markers only, no line) if data is provided
    if dates and prices:
        # Default: all cyan if no chain info provided
        if ad_chains is None:
            ad_chains = [(i, True) for i in range(len(dates))]

        # Draw connecting lines for chained ads
        for i in range(len(dates) - 1):
            idx, is_end = ad_chains[i]
            # If this ad is not the end of chain, draw line to next ad
            if not is_end and i + 1 < len(dates):
                ax.plot([dates[i], dates[i + 1]], [prices[i], prices[i + 1]],
                       color='#006b6b', linestyle='-', linewidth=1, zorder=1)

        # Plot dots with colors based on chain status
        for i, (idx, is_end) in enumerate(ad_chains):
            color = '#00FFFF' if is_end else '#006b6b'
            ax.plot(dates[i], prices[i], marker='o', linestyle='', markersize=3, color=color, zorder=2)

    # Styling to match the retro theme
    fig.patch.set_facecolor('#1a1a1a')
    ax.set_facecolor('#2a2a2a')
    ax.spines['bottom'].set_visible(False)
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    ax.spines['left'].set_visible(False)
    ax.tick_params(axis='x', colors='#ffffff', labelsize=7)
    ax.tick_params(axis='y', colors='#ffffff', labelsize=7)

    # Move y-axis ticks to the right, but keep the label on the left
    ax.yaxis.tick_right()
    ax.yaxis.set_label_position("left")

    # Set x-axis limits to always show exactly one year
    current_date = datetime.now()
    one_year_ago = current_date - timedelta(days=365)
    ax.set_xlim(one_year_ago, current_date)

    # Format the x-axis to show dates nicely
    # Create manual tick positions every 2 months from one_year_ago
    tick_dates = []
    tick_date = one_year_ago
    while tick_date <= current_date:
        tick_dates.append(tick_date)
        tick_date = tick_date + timedelta(days=60)  # Approximately 2 months

    ax.xaxis.set_major_locator(FixedLocator([mdates.date2num(d) for d in tick_dates]))
    ax.xaxis.set_major_formatter(mdates.DateFormatter('%b\n%y'))
    plt.setp(ax.xaxis.get_majorticklabels(), rotation=0, ha='center')

    # Add labels
    ax.set_ylabel('Price hist. (€)', color='#ffffff', fontsize=8)
    ax.grid(True, alpha=0.2, color='#929292')

    # Add "No data" text if requested and no data provided
    if no_data and (not dates or not prices):
        # Hide the y-axis tick labels when there's no data, but keep the label
        ax.set_yticklabels([])
        ax.tick_params(axis='y', length=0)

        ax.text(0.5, 0.5, 'No data',
                transform=ax.transAxes,
                fontsize=12,
                color='#666666',
                ha='center',
                va='center',
                style='italic')

    # Tight layout to maximize space usage and minimize left padding
    plt.tight_layout(pad=0.1)
    plt.subplots_adjust(left=0.01)

    # Save the figure in the requested format
    save_format = format.lower()
    if save_format not in ['svg', 'png']:
        save_format = 'svg'  # Default to SVG if invalid format

    plt.savefig(output_path, format=save_format, facecolor=fig.get_facecolor(), edgecolor='none', bbox_inches='tight')
    plt.close(fig)

    # Return the filename (basename)
    return os.path.basename(output_path)


def generate_nodata_graph(output_path: str, format: str = 'svg') -> str:
    """Generate an empty price timeline graph (no data) and save it to disk.

    Args:
        output_path: Full path where the graph should be saved
        format: Output format ('svg' or 'png')

    Returns:
        str: The filename (basename) of the saved graph

    Raises:
        Exception: If graph generation fails
    """
    # Call generate_price_graph with no_data flag
    return generate_price_graph([], [], output_path, no_data=True, format=format)
