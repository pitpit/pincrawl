# PinCrawl - Web Crawling Tool

A project for scraping and matching products/ads

## Files
- `docker-compose.yml` – Defines the `app` and `postgres` services
- `requirements.txt` – Dependencies including Click for CLI functionality and PostgreSQL support
- `cli.py` – Main CLI application with `pincrawl` command
- `database.py` – PostgreSQL database models and connection management
- `.dockerignore` – Keeps build context lean

## Quick Start

Setup environment variables:
```bash
cp .env.dist .env
# Edit .env and add your API keys (Firecrawl, OpenAI, Pinecone)
```

Start the service:
```bash
docker-compose run --rm app bash
```

Initialize the database:
```bash
pincrawl init
```

Show help:
```bash
pincrawl --help
```

Run a crawling task to discover ads:
```bash
pincrawl -vvv crawl
```

Scrape detailed information from discovered ads:
```bash
pincrawl -vvv scrape
```
Scrape detailed information from discovered ads:
```bash
pincrawl -vvv identify
```

## Quick Start

Dev installation:
```bash
pip install -e .
```

Prod installation:
```bash
pip install .
```