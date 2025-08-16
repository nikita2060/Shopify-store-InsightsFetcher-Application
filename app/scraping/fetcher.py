import asyncio, httpx, tldextract, re
from contextlib import asynccontextmanager
from typing import Optional
from app.core.config import settings
from app.core.logging import log

def normalize_url(url: str) -> str:
    url = url.strip()
    if not re.match(r'^https?://', url):
        url = 'https://' + url
    url = url.rstrip('/')
    return url

async def is_shopify_like(client: httpx.AsyncClient, base: str) -> bool:
    try:
        r = await client.get(base + "/", follow_redirects=True, timeout=settings.INSIGHTS_TIMEOUT)
        if r.status_code >= 400:
            return False
        # Heuristics: look for cdn.shopify.com assets, theme JS, or Shopify meta tags
        txt = r.text.lower()
        return ("cdn.shopify.com" in txt) or ("myshopify.com" in txt) or ("shopify" in txt and "theme" in txt)
    except Exception:
        return False

@asynccontextmanager
async def client_ctx():
    limits = httpx.Limits(max_keepalive_connections=20, max_connections=40)
    headers = {"User-Agent": settings.INSIGHTS_USER_AGENT, "Accept-Encoding": "gzip, deflate"}
    async with httpx.AsyncClient(headers=headers, limits=limits, http2=True) as client:
        yield client
