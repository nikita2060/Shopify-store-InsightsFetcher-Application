from __future__ import annotations
import asyncio, datetime, urllib.parse
from typing import Optional, List
from app.core.config import settings
from app.schemas.models import BrandContext
from app.scraping.fetcher import client_ctx, normalize_url, is_shopify_like
from app.scraping.async_scraper import AsyncShopifyScraper
from app.scraping.discovery import (
    discover_policy_urls, discover_faq_urls, discover_about_url, discover_contact_url
)
from app.scraping.extractors import (
    fetch_all_products, hero_products_from_home,
    extract_policy, extract_faqs, extract_socials,
    extract_contacts, extract_important_links,
    extract_about_text, extract_brand_name_from_ld, fetch_text
)
from app.db import SessionLocal, init_db
from app import models


async def gather_insights(website_url: str) -> Optional[BrandContext]:
    base = normalize_url(website_url)
    async with client_ctx() as client:
        ok = await is_shopify_like(client, base)
        if not ok:
            return None

        r = await client.get(base + "/", follow_redirects=True, timeout=settings.INSIGHTS_TIMEOUT)
        home_html = r.text

        # concurrent tasks
        products_task = asyncio.create_task(
            fetch_all_products(client, base, cap=settings.INSIGHTS_MAX_PRODUCTS)
        )
        faq_urls_task = asyncio.create_task(discover_faq_urls(client, base, home_html))
        about_url_task = asyncio.create_task(discover_about_url(client, base, home_html))
        contact_url_task = asyncio.create_task(discover_contact_url(client, base, home_html))
        policies_task = asyncio.create_task(discover_policy_urls(client, base, home_html))

        catalog = await products_task
        faq_urls = await faq_urls_task
        about_url = await about_url_task
        contact_url = await contact_url_task
        policy_pairs = await policies_task

        heroes = await hero_products_from_home(client, base, home_html, catalog)

        # extract policies
        policies = []
        for typ, url in policy_pairs:
            pol = await extract_policy(client, url, typ)
            if pol:
                policies.append(pol)

        faqs = await extract_faqs(client, faq_urls) if faq_urls else []
        socials = extract_socials(home_html, base)
        contacts = extract_contacts(home_html, base, contact_url)
        important_links = extract_important_links(home_html, base)

        about_text = None
        brand_name = extract_brand_name_from_ld(home_html, base + "/")

        if about_url:
            about_html = await fetch_text(client, about_url) or ""
            about_text = extract_about_text(about_html) or about_text
            brand_name = brand_name or extract_brand_name_from_ld(about_html, about_url)

        ctx = BrandContext(
            website=base,
            brand_name=brand_name,
            about_text=about_text,
            hero_products=heroes,
            product_catalog=catalog,
            policies=policies,
            faqs=faqs,
            socials=socials,
            contacts=contacts,
            important_links=important_links,
            fetched_at=datetime.datetime.utcnow(),
            meta={"source": "shopify-insights-fetcher", "version": "1.0.0"},
        )
        return ctx


async def gather_insights_and_persist(website_url: str) -> Optional[BrandContext]:
    ctx = await gather_insights(website_url)
    if ctx is None:
        return None

    init_db()
    db = SessionLocal()
    try:
        domain = ctx.website
        brand = db.query(models.Brand).filter(models.Brand.domain == domain).first()

        if not brand:
            brand = models.Brand(
                domain=domain,
                name=ctx.brand_name,
                about_text=ctx.about_text,
                fetched_at=ctx.fetched_at,
                meta=ctx.meta,
            )
            db.add(brand)
            db.commit()
            db.refresh(brand)
        else:
            brand.name = ctx.brand_name
            brand.about_text = ctx.about_text
            brand.fetched_at = ctx.fetched_at
            brand.meta = ctx.meta
            db.commit()

        # replace products
        db.query(models.Product).filter(models.Product.brand_id == brand.id).delete()
        for p in ctx.product_catalog:
            prod = models.Product(
                brand_id=brand.id,
                handle=p.handle,
                title=p.title,
                url=str(p.url) if p.url else None,
                images=p.images,
                price=str(p.price) if p.price else None,
                currency=p.currency,
                sku=p.sku,
                tags=p.tags,
                variants=p.variants,
                raw=p.raw,
            )
            db.add(prod)
        db.commit()

        # replace policies
        db.query(models.Policy).filter(models.Policy.brand_id == brand.id).delete()
        for pol in ctx.policies:
            db.add(
                models.Policy(
                    brand_id=brand.id,
                    type=pol.type,
                    url=str(pol.url),
                    content_text=pol.content_text,
                    content_html=pol.content_html,
                )
            )
        db.commit()

        # replace FAQs
        db.query(models.FAQ).filter(models.FAQ.brand_id == brand.id).delete()
        for f in ctx.faqs:
            db.add(
                models.FAQ(
                    brand_id=brand.id,
                    question=f.question,
                    answer=f.answer,
                    url=str(f.url) if f.url else None,
                )
            )
        db.commit()

        # replace socials
        db.query(models.Social).filter(models.Social.brand_id == brand.id).delete()
        for s in ctx.socials:
            db.add(
                models.Social(
                    brand_id=brand.id,
                    platform=s.platform,
                    url=str(s.url),
                    handle=s.handle,
                )
            )
        db.commit()
    finally:
        db.close()

    return ctx


# competitor_insights uses DuckDuckGo HTML search to find candidate Shopify stores and runs gather_insights on them
async def competitor_insights(website_url: str, limit: int = 3):
    base = normalize_url(website_url)
    async with client_ctx() as client:
        r = await client.get(base + "/", follow_redirects=True, timeout=settings.INSIGHTS_TIMEOUT)
        home_html = r.text

        brand_name = extract_brand_name_from_ld(home_html, base + "/") or ""
        domain_name = urllib.parse.urlparse(base).hostname or ""
        keywords = (brand_name or domain_name).split()
        query = "+".join([urllib.parse.quote_plus(k) for k in keywords if k]) or urllib.parse.quote_plus(domain_name)

        search_url = f"https://duckduckgo.com/html/?q={query}+shopify"
        resp = await client.get(search_url, follow_redirects=True, timeout=15)

        links = []
        if resp.status_code == 200:
            from selectolax.parser import HTMLParser
            tree = HTMLParser(resp.text)
            for a in tree.css("a[href]")[:60]:
                href = a.attributes.get("href", "")
                if "uddg=" in href:
                    import urllib.parse as up
                    try:
                        p = up.parse_qs(up.urlparse(href).query).get("uddg", [href])[0]
                        href = p
                    except Exception:
                        pass
                if href and ("myshopify.com" in href or "/products/" in href or href.startswith("http")):
                    if href not in links:
                        links.append(href)
                if len(links) >= limit:
                    break

        comps = []
        for l in links[:limit]:
            u = l.split("?")[0].rstrip("/")
            comps.append(u)

        results = []
        for c in comps:
            try:
                ins = await gather_insights(c)
                if ins:
                    results.append({"website": c, "insights": ins})
            except Exception:
                continue

        return {"source": base, "competitors_found": len(results), "results": results}



async def gather_insights_async_wrapper(website_url: str):
    """Backward-compatible wrapper that uses AsyncShopifyScraper to enrich data"""
    scraper = AsyncShopifyScraper(website_url)
    data = await scraper.scrape()
    return data
