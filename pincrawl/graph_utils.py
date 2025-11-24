"""Utilities for generating price timeline graphs for pinball machines."""

import os
from typing import List, Tuple, Optional
from datetime import datetime, timedelta
import matplotlib
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from matplotlib.ticker import FixedLocator


def generate_price_graph(dots: List[Tuple[datetime, float, int, Optional[int], bool]], output_path: str, no_data: bool = False, format: str = 'svg') -> str:
    """Generate a price timeline graph and save it to disk.

    Args:
        dots: List of tuples (datetime, price, id, next_id, is_end_of_chain) where:
            - datetime: Date when ad was created
            - price: Price in euros
            - id: Ad ID
            - next_id: ID of the next ad in the chain (None if this is the last)
            - is_end_of_chain: Boolean indicating if this ad is the end of a chain
        output_path: Full path where the graph should be saved
        no_data: If True and no data, show "No data" text in center
        format: Output format ('svg' or 'png')

    Raises:
        Exception: If graph generation fails
    """
    matplotlib.use('Agg')  # Use non-interactive backend

    # Create output directory if it doesn't exist
    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    # Create figure with specific size (320px wide x 120px high at 100 DPI)
    fig, ax = plt.subplots(figsize=(3.2, 1.2), dpi=100)

    # Plot the data (markers only, no line) if data is provided
    if dots:
        # Draw connecting lines for chained ads based on next_id
        for i, (date, price, ad_id, next_id, is_end) in enumerate(dots):
            if next_id is not None:
                # Find the next ad in the list by matching next_id
                for j, (next_date, next_price, next_ad_id, _, _) in enumerate(dots):
                    if next_ad_id == next_id:
                        # Draw line from current ad to next ad
                        ax.plot([date, next_date], [price, next_price],
                               color='#006b6b', linestyle='-', linewidth=1, zorder=1)
                        break

        # Plot dots with colors based on chain status
        for date, price, ad_id, next_id, is_end in dots:
            color = '#00FFFF' if is_end else '#006b6b'
            ax.plot(date, price, marker='o', linestyle='', markersize=3, color=color, zorder=2)
    else:
        # Add "No data" text
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
