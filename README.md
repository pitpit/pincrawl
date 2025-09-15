# PinCrawl - Web Crawling Tool

A simple web crawling CLI tool built with Python and Click, containerized with Docker Compose.

## Files
- `docker-compose.yml` – Defines the `app` service using `python:3.12-slim` image.
- `requirements.txt` – Dependencies including Click for CLI functionality.
- `cli.py` – Main CLI application with `pincrawl` command.
- `.dockerignore` – Keeps build context lean.

## Quick Start

Setup environment variables:
```bash
cp .env.dist .env
# Edit .env and add your Firecrawl API key
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
