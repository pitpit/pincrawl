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

Start the console:
```bash
docker-compose run --rm console bash
pip install -e .
```

Show help:
```bash
pincrawl --help
```

Run a crawling task to discover ads:
```bash
pincrawl -vvv ads crawl
```

Scrape detailed information from discovered ads:
```bash
pincrawl -vvv ads scrape
```

Display price statistics (read-only):
```bash
pincrawl ads stats
```

Display and save statistics:
```bash
pincrawl ads stats --save
```


## Cronjobs

First cronjob runs every 5minutes between 8o am and midnight (utc+2):

```
*/5 6-23 * * * pincrawl crawl >> /var/log/pincrawl.log 2>&1
```

Second cronjob runs every 5minutes between 8o am and midnight (utc+2), but 2min after:

```
2-59/5 6-23 * * * pincrawl scrape >> /var/log/pincrawl.log 2>&1
```

Third cronjob runs every 5minutes between 8o am and midnight (utc+2), but 2min after:

```
4-59/5 6-23 * * * pincrawl subs send >> /var/log/pincrawl.log 2>&1
```

Fourth cronjob runs every night:

```
0 2 * * * pincrawl ads stats --save >> /var/log/pincrawl.log 2>&1
```

## Translations

The project uses a shared translation directory at the root level (`/translations/`) for both the website and CLI/email services.

### Update translation strings:
```bash
pybabel extract -F babel.cfg -o new.po . && pybabel update -i new.po -d translations && rm new.po
```

### Compile all translation files:
```bash
pybabel compile -d translations
```

Translation files are located in:
- `translations/en/LC_MESSAGES/messages.po` (English)
- `translations/fr/LC_MESSAGES/messages.po` (French)

## TODO

- [ ] Enhance leboncoin search with typo (fliper, filpper)
- [ ] Add other ads providers: ebay, ouest france
- [ ] Price history only for Collector and Pro
- [ ] thumbnails for pinball
- [ ] pink dot for current ad price in graph (in email notification)
- [ ] manual fix / product check for ads
- [ ] use internal id of product as a foreign key in Watching instead of opdb_id
- [ ] check opdb_id when creating a Watching
- [ ] unwatch pinball from email
- [ ] download image and visit archive (or do a screenshot)
- [ ] CGU
- [ ] better logo
- [ ] setup stripe
- [ ] setup mailersend
- [ ] translate svg/png price graph files
- [ ] créer une tâche d'envoie par destinaire pour pouvoir rejouer en cas de plantage
- [ ] améliorer le moteur de recherche
- [X] rename page /pricing to /plans
- [X] add a bcc mailcatcher to all sent mails
- [X] remove validate_locale everywhere
- [X] use internal id of the user as a foreign key in Watching entity instead of email
- [X] traduire le mail en FR (email template now supports EN/FR translation)
- [X] limit number of subscriptions to 3 / user
- [X] mentions legales
- [X] custom domain pincrawl.pitp.it

## 3rd party tools

* https://app.mailersend.com/dashboard
* https://dashboard.render.com/
* https://platform.openai.com/
* https://www.firecrawl.dev/app/logs
* https://app.pinecone.io/