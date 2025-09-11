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
docker compose run --rm app python cli.py init
```

Show help:
```bash
docker compose run --rm app python cli.py --help
```

Run a crawling task to discover ads:
```bash
docker compose run --rm app python cli.py crawl --verbose
```

Scrape detailed information from discovered ads:
```bash
docker compose run --rm app python cli.py scrape --verbose --limit 10
```

## Environment Variables

- `PINCRAWL_DB_NAME`: Database filename (default: `pincrawl.db`)
- `FIRECRAWL_API_KEY`: Your Firecrawl API key (required) - Get one at https://firecrawl.dev

Example with custom database name:
```bash
docker compose run --rm -e PINCRAWL_DB_NAME=my_custom.db app python cli.py init
docker compose run --rm -e PINCRAWL_DB_NAME=my_custom.db app python cli.py run
```

Run with URL parameter:
```bash
docker compose run --rm app python cli.py run --url https://example.com
```

Run with all options:
```bash
docker compose run --rm app python cli.py run --url https://example.com --depth 2 --output results.json --verbose
```

## Available Commands

- `pincrawl run` - Run a web crawling task
  - `--url, -u` - URL to crawl
  - `--depth, -d` - Crawl depth (default: 1)
  - `--output, -o` - Output file path
  - `--verbose, -v` - Enable verbose output

## Development

Open an interactive Python REPL:
```bash
docker compose run --rm app python
```

Run any Python command:
```bash
docker compose run --rm app python -c "print('hello from docker')"
```

## Notes
- Source directory is mounted into the container, so edits on the host are immediately visible.
- Uses the official `python:3.12-slim` image from Docker Hub - no custom build required.
- The container runs as root by default for simplicity; you can add a non-root user later if desired.
- For performance on macOS/Windows, consider using Docker volumes or delegated mounts if file I/O becomes slow.

## Next Steps (Optional Enhancements)
- Implement actual web crawling logic in `cli.py`
- Add more subcommands (e.g., `pincrawl config`, `pincrawl status`)
- Add linting / formatting (e.g. `ruff`, `black`).
- Add a test framework (`pytest`) and CI workflow.
- Create a custom Dockerfile for production use with pre-installed dependencies.

Enjoy hacking! 🚀
