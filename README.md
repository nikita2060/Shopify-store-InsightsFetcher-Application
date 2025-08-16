# Shopify Store Insights-Fetcher (FastAPI)

A robust, async FastAPI backend that fetches insights from Shopify stores (without the official Shopify API) and returns a structured Brand Context JSON.

## Features (Mandatory)
- Whole Product Catalog via `/products.json` pagination (fallback to HTML discovery if needed)
- Hero Products (from home page product links / JSON-LD)
- Policies: Privacy, Refund/Return, Terms, Shipping (auto-discovery)
- FAQs (accordions, Q/A patterns, per-page fallback)
- Social Handles (Instagram, Facebook, TikTok, X/Twitter, YouTube, Pinterest, LinkedIn)
- Contact details (emails, phones, addresses, contact page)
- Brand text context (About page extraction + JSON-LD Organization)
- Important links (Order tracking, Contact Us, Blogs, Sitemap, etc.)
- Clear error mapping: 401 (website not found), 500 (internal error)

## Quickstart
```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
# Swagger UI at http://localhost:8000/docs
```

### Example
```bash
curl -X POST http://localhost:8000/insights       -H "Content-Type: application/json"       -d '{"website_url":"https://memy.co.in"}'
```

## Docker
```bash
docker build -t shopify-insights .
docker run -p 8000:8000 shopify-insights
```

## Notes
- Respects robots.txt for politeness (basic).
- Bounded concurrency & retries using httpx.
- Easily extensible extractors in `app/scraping/`.
- Bonus DB schema files included but not wired by default—see `models/` and `alembic/` placeholders if you extend.
\n\n## Persistence and Bonus Features\n- Added SQLAlchemy persistence (defaults to SQLite). Set DATABASE_URL to MySQL DSN to use MySQL.\n- Use `?persist=true` on `/insights` to store results.\n- New `/competitors` endpoint does best-effort competitor discovery via DuckDuckGo and returns their insights.\n\n\n## Final Supercharged Build\n- Merged async scraper (better hero/product/policy discovery)\n- Added SEO meta extraction and Price/Discount analytics\n- API param `?mode=full` uses the async scraper and returns SEO & price insights inside `meta` in the BrandContext response.\n