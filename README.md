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

Generate VAPID keys for Web Push notifications:
```bash
npx web-push generate-vapid-keys
```
And copy the env vars into your .env file.

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

Send email notifications to watchers:
```bash
pincrawl watching send-email
```

Send push notifications to watchers:
```bash
pincrawl watching send-push
```

Send both email and push notifications:
```bash
pincrawl watching send
```

## Testing Push Notifications

To test push notifications for a logged-in user, you can use the test endpoint:

```bash
# Replace 'en' with your locale and ensure you're authenticated in the browser first
curl -X POST "http://localhost:8000/test-push-notification" \
  -H "Content-Type: application/json" \
  -H "Cookie: session=your_session_cookie_here"
```

Note: You need to be logged in and have push notifications enabled in your account settings for this to work.

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

- [] rework graph_utils.py to make a class GraphService
- [X] Web Push API
- [ ] maintenir la persistence? Add periodic background sync


- [ ] Accelerate cron running everything in one time merging all together with a global command invoking scrape, crawl, send: pincrawl run
- [ ] Ad images in push notification
- [ ] Ad images in email
- [ ] ad a parameter --since to send everything from a date (debug) when running `pincrawl watching send`
- [ ] rework send_ad_notification_email() to not build a ad_data dictionnary and directly pass "ads" var
- [ ] cdn.tailwindcss.com should not be used in production
- [ ] main:watch(), main:update_my_account() shoud respond a JsonResponse
- [ ] rework JS: one file, use a binding framework
- [ ] Install webapp on desktop
- [ ] passer auth0 en mode prod
- [ ] active menu item in header depending on current page
- [ ] OPEN TO THE WORLD
- [ ] Enhance leboncoin search with typo (fliper, filpper)
- [ ] Add other ads providers: ebay, ouest france
- [ ] Price history only for Collector and Pro
- [ ] thumbnails for pinball
- [ ] pink dot for current ad price in graph (in email notification)
- [ ] manual fix / product check for ads
- [ ] use internal id of product as a foreign key in Watching instead of opdb_id

will allow to remove
```
                    if ad.opdb_id:
                        product = session.query(Product).filter_by(opdb_id=ad.opdb_id).first()
                        if product:
                            # Use the dynamic graph endpoint with product_id (PNG for better email client support)
                            ad_info['graph_url'] = f"{self.base_url}/graphs/{product.id}.png"
```

- [ ] check opdb_id when creating a Watching
- [ ] unwatch pinball from email
- [ ] download image and visit archive (or do a screenshot)
- [ ] better logo
- [ ] setup stripe
- [ ] translate svg/png price graph files
- [ ] créer une tâche d'envoie par destinaire pour pouvoir rejouer en cas de plantage
- [ ] améliorer le moteur de recherche
- [X] sauvegarder le vendeur
- [X] CGU
- [X] setup mailersend
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