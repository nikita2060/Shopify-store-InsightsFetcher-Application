from __future__ import annotations
import re, asyncio
from typing import List, Dict, Optional, Tuple
from urllib.parse import urljoin
import httpx
from selectolax.parser import HTMLParser

POLICY_CANDIDATES = [
    ("privacy", ["privacy-policy","privacy","policies/privacy-policy"]),
    ("refund", ["refund-policy","refund","return-policy","policies/refund-policy","policies/return-policy"]),
    ("return", ["return","returns"]),
    ("shipping", ["shipping-policy","shipping","delivery"]),
    ("terms", ["terms-of-service","terms","tos"]),
]

def find_links_by_keywords(html: str, base: str, keywords: List[str]) -> List[str]:
    tree = HTMLParser(html)
    links = []
    for a in tree.css("a[href]"):
        href = a.attributes.get("href","")
        text = (a.text() or "").lower()
        for kw in keywords:
            if kw in href.lower() or kw in text:
                links.append(urljoin(base, href))
    return list(dict.fromkeys(links))

async def fetch_text(client: httpx.AsyncClient, url: str) -> str:
    r = await client.get(url, follow_redirects=True)
    r.raise_for_status()
    return r.text

async def discover_sitemaps(client: httpx.AsyncClient, base: str) -> List[str]:
    candidates = ["/sitemap.xml", "/sitemap_index.xml"]
    sitemaps = []
    for c in candidates:
        try:
            r = await client.get(base + c, follow_redirects=True)
            if r.status_code == 200 and ("<urlset" in r.text or "<sitemapindex" in r.text):
                sitemaps.append(base + c)
        except Exception:
            pass
    return sitemaps

async def discover_policy_urls(client: httpx.AsyncClient, base: str, home_html: str) -> List[Tuple[str,str]]:
    found = []
    # First, try canonical Shopify policy routes
    canonical = [
        (t, f"{base}/policies/{slug}") for t, slugs in POLICY_CANDIDATES for slug in slugs if slug.startswith("policies/")
    ]
    for t, url in canonical:
        try:
            r = await client.get(url, follow_redirects=True)
            if r.status_code == 200 and len(r.text) > 400:
                found.append((t, url))
        except Exception:
            pass
    # Next, scan home page footer/header
    for t, slugs in POLICY_CANDIDATES:
        links = find_links_by_keywords(home_html, base, slugs)
        for l in links:
            if (t,l) not in found:
                found.append((t,l))
    return found

def extract_product_links_from_home(home_html: str, base: str, limit: int = 24) -> List[str]:
    tree = HTMLParser(home_html)
    links = []
    for a in tree.css('a[href]'):
        href = a.attributes.get("href","")
        if re.search(r"/products/[^/]+/?$", href):
            links.append(urljoin(base, href))
    deduped = list(dict.fromkeys(links))
    return deduped[:limit]

async def discover_faq_urls(client: httpx.AsyncClient, base: str, home_html: str) -> List[str]:
    keywords = ["faq","faqs","help","support","returns","shipping"]
    links = find_links_by_keywords(home_html, base, keywords)
    return links[:8]

async def discover_about_url(client: httpx.AsyncClient, base: str, home_html: str) -> Optional[str]:
    for kw in ["about","about-us","our-story"]:
        links = find_links_by_keywords(home_html, base, [kw])
        if links:
            return links[0]
    return None

async def discover_contact_url(client: httpx.AsyncClient, base: str, home_html: str) -> Optional[str]:
    for kw in ["contact","contact-us","support","help"]:
        links = find_links_by_keywords(home_html, base, [kw])
        if links:
            return links[0]
    return None
