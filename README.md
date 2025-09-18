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
pip install -e .
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

## Quick Start

Dev installation:
```bash
pip install -e .
```

Prod installation:
```bash
pip install .
```

## Cronjobs

First cronjob runs every 5minutes between 8o am and midnight (utc+2):

```
*/5 6-21 * * * pincrawl crawl >> /var/log/pincrawl.log 2>&1
```

Second cronjob runs every 5minutes between 8o am and midnight (utc+2), but 2min after:

```
2-59/5 6-21 * * * pincrawl scrape --limit=5 >> /var/log/pincrawl.log 2>&1
```

## TODO

- check opdb_id when creating a subscription