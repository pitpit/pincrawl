#!/usr/bin/env python3

import click
from tinydb import TinyDB, Query
import os
import json
from dotenv import load_dotenv
import openai

# Load environment variables from .env file
load_dotenv()

# Global configuration
DB_NAME = os.getenv("PINCRAWL_DB_NAME", "pincrawl.db")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

@click.group()
def products():
    """Manage and view products in the database."""
    pass

@products.command("query")
@click.argument("query", required=True)
@click.option("--limit", "-l", type=int, default=5, help="Number of results to return (default: 5)")
@click.option("--verbose", "-v", is_flag=True, help="Enable verbose output")
def query_products(query, limit, verbose):
    """Identify products using ChatGPT's knowledge base."""

    # Check if required API key is available
    if not OPENAI_API_KEY:
        raise click.ClickException("OPENAI_API_KEY environment variable is required.")


    try:
        # Initialize OpenAI
        openai.api_key = OPENAI_API_KEY

        if verbose:
            click.echo(f"Query: '{query}'")

        # Create prompt for ChatGPT to identify products based on its knowledge
        prompt = f"""
        You are a product identification expert specializing in pinball machines and arcade games.

        User query: "{query}"

        Based on your knowledge, identify up to {limit} real pinball machines or arcade games that best match this query.

        Return your response as a JSON array containing objects with the following structure:
        [
            {{
                "name": "exact product name",
                "manufacturer": "manufacturer name",
                "year": "year of release as a json number or null",
                "reason": "brief explanation of why it matches",
                "features": "notable features or characteristics"
            }}
        ]

        If you cannot identify any relevant pinball machines for this query, return an empty array: []

        Focus on real, commercially released products. Be as specific as possible with product names and manufacturers.
        Only return valid JSON - no additional text or formatting.
        """

        if verbose:
            click.echo("Querying ChatGPT for product identification...")

        completion = openai.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.1  # Low temperature for more consistent results
        )

        response_text = completion.choices[0].message.content

        # Parse the JSON response to validate it, then display directly
        try:
            matches = json.loads(response_text)

            if not isinstance(matches, list):
                click.echo("Invalid response format: expected JSON array.")
                if verbose:
                    click.echo("Raw response:")
                    click.echo(response_text)
                return

        except json.JSONDecodeError as e:
            click.echo(f"Failed to parse JSON response: {str(e)}")
            if verbose:
                click.echo("Raw response:")
                click.echo(response_text)
            return

        # Display the JSON response directly
        click.echo(json.dumps(matches, indent=2))

    except Exception as e:
        raise click.ClickException(f"Failed to query products: {str(e)}")