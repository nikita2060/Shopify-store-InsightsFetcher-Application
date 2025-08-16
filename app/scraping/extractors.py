from __future__ import annotations
import re, asyncio, json
from typing import List, Dict, Any, Optional
from urllib.parse import urljoin, urlparse
import httpx
from selectolax.parser import HTMLParser
import trafilatura
import extruct
from w3lib.html import get_base_url
from app.schemas.models import Product, Policy, FAQ, SocialHandle, ContactInfo, ImportantLinks

PRODUCT_PAGE_RE = re.compile(r"/products/[^/]+/?$")

async def fetch_json(client: httpx.AsyncClient, url: str) -> Optional[dict]:
    r = await client.get(url, follow_redirects=True)
    if r.status_code == 200:
        try:
            return r.json()
        except Exception:
            return None
    return None

async def fetch_text(client: httpx.AsyncClient, url: str) -> Optional[str]:
    r = await client.get(url, follow_redirects=True)
    if r.status_code == 200:
        return r.text
    return None

# ---------- Products via products.json ----------
async def fetch_all_products(client: httpx.AsyncClient, base: str, cap: int = 2000) -> List[Product]:
    page = 1
    out: List[Product] = []
    per_page = 250
    while True:
        url = f"{base}/products.json?limit={per_page}&page={page}"
        r = await client.get(url, follow_redirects=True)
        if r.status_code != 200:
            # try collections all
            if page == 1:
                url2 = f"{base}/collections/all/products.json?limit={per_page}&page={page}"
                r2 = await client.get(url2, follow_redirects=True)
                if r2.status_code != 200:
                    break
                data = r2.json()
            else:
                break
        else:
            data = r.json()
        products = data.get("products") or []
        if not products:
            break
        for p in products:
            urlp = urljoin(base, f"/products/{p.get('handle','')}")
            variants = []
            for v in (p.get("variants") or []):
                variants.append({
                    "id": v.get("id"),
                    "title": v.get("title"),
                    "price": safe_float(v.get("price")),
                    "available": v.get("available"),
                    "sku": v.get("sku")
                })
            out.append(Product(
                handle=p.get("handle"),
                title=p.get("title"),
                url=urlp,
                images=[img.get("src") for img in (p.get("images") or []) if img.get("src")],
                price=safe_float((p.get("variants") or [{}])[0].get("price")) if p.get("variants") else None,
                currency=None,
                sku=[v.get("sku") for v in (p.get("variants") or []) if v.get("sku")],
                tags=ensure_list(p.get("tags")),  # <-- FIXED
                variants=variants,
                raw=p
            ))
            if len(out) >= cap:
                return out
        if len(products) < per_page:
            break
        page += 1
    return out

# helper: make sure tags are always a list
def ensure_list(value):
    if isinstance(value, list):
        return value
    if isinstance(value, str):
        return [v.strip() for v in value.split(",") if v.strip()]
    return []

def safe_float(x):
    try:
        return float(x)
    except Exception:
        return None

# ---------- Hero Products (from home or JSON-LD) ----------
async def hero_products_from_home(client: httpx.AsyncClient, base: str, home_html: str, catalog: List[Product]) -> List[Product]:
    links = []
    tree = HTMLParser(home_html)
    for a in tree.css("a[href]"):
        href = a.attributes.get("href","")
        if PRODUCT_PAGE_RE.search(href):
            links.append(urljoin(base, href))
    # map to catalog or scrape minimal info
    catalog_by_url = {p.url: p for p in catalog if p.url}
    heroes: List[Product] = []
    for u in dict.fromkeys(links):  # preserve order & dedupe
        if u in catalog_by_url:
            heroes.append(catalog_by_url[u])
        else:
            # scrape product title from product page quickly
            html = await fetch_text(client, u)
            if not html:
                continue
            treep = HTMLParser(html)
            title = (treep.css_first("h1") or treep.css_first("meta[property='og:title']")).text(strip=True) if treep.css_first("h1") else None
            heroes.append(Product(url=u, title=title))
        if len(heroes) >= 12:
            break
    return heroes

# ---------- Policies ----------
async def extract_policy(client: httpx.AsyncClient, url: str, typ: str) -> Optional[Policy]:
    html = await fetch_text(client, url)
    if not html:
        return None
    text = trafilatura.extract(html, include_comments=False, include_tables=False) or None
    return Policy(type=typ, url=url, content_html=html, content_text=text)

# ---------- FAQs ----------
def parse_faqs_from_html(html: str, base: str, page_url: str) -> List[dict]:
    tree = HTMLParser(html)
    faqs = []
    # details/summary
    for d in tree.css("details"):
        qnode = d.css_first("summary")
        anode = d
        if qnode:
            q = qnode.text().strip()
            a = (anode.text(separator=" ").strip() if anode else "").replace(q, "", 1).strip()
            if q and a:
                faqs.append({"question": q, "answer": a, "url": page_url})
    # common classes
    qa_pairs = []
    questions = tree.css(".question, .faq-question, h2, h3, h4")
    for qn in questions:
        q = qn.text().strip()
        # next sibling paragraph or div
        sib = qn.next
        while sib and sib.tag in ("#text",):
            sib = sib.next
        if sib and sib.tag in ("p","div","section","article"):
            a = sib.text(separator=" ").strip()
            if q and a and len(a) > 5:
                qa_pairs.append((q, a))
    for q,a in qa_pairs:
        faqs.append({"question": q, "answer": a, "url": page_url})
    # de-dup
    uniq = []
    seen = set()
    for f in faqs:
        key = (f["question"][:80].lower(), f["answer"][:80].lower())
        if key not in seen:
            uniq.append(f); seen.add(key)
    return uniq[:50]

async def extract_faqs(client: httpx.AsyncClient, urls: List[str]) -> List[FAQ]:
    out: List[FAQ] = []
    for u in urls[:5]:
        html = await fetch_text(client, u)
        if not html:
            continue
        for f in parse_faqs_from_html(html, u, u):
            out.append(FAQ(**f))
    # dedupe by question
    seen = set(); uniq = []
    for f in out:
        if f.question.lower() not in seen:
            uniq.append(f); seen.add(f.question.lower())
    return uniq[:60]

# ---------- Socials ----------
SOCIAL_DOMAINS = {
    "instagram": "instagram.com",
    "facebook": "facebook.com",
    "tiktok": "tiktok.com",
    "twitter": "twitter.com",
    "x": "x.com",
    "youtube": "youtube.com",
    "pinterest": "pinterest.com",
    "linkedin": "linkedin.com",
}

def extract_socials(html: str, base: str) -> List[SocialHandle]:
    tree = HTMLParser(html)
    found = []
    for a in tree.css("a[href]"):
        href = a.attributes.get("href","")
        for platform, domain in SOCIAL_DOMAINS.items():
            if domain in href:
                handle = None
                try:
                    path = urlparse(href).path.strip("/")
                    handle = path.split("/")[0] if path else None
                except Exception:
                    pass
                found.append(SocialHandle(platform=platform, url=href, handle=handle))
    # dedupe by platform
    out = []
    seen = set()
    for s in found:
        key = s.platform
        if key not in seen:
            out.append(s); seen.add(key)
    return out

# ---------- Contact Info ----------
EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
PHONE_RE = re.compile(r"(?:\+\d{1,3}[-.\s]?)?(?:\(?\d{2,4}\)?[-.\s]?)?\d{3,4}[-.\s]?\d{3,4}")

def extract_contacts(html: str, base: str, contact_url: Optional[str]) -> ContactInfo:
    tree = HTMLParser(html)
    emails = set()
    phones = set()
    text = tree.text(separator=" ")
    for m in EMAIL_RE.findall(text or ""):
        emails.add(m)
    for m in PHONE_RE.findall(text or ""):
        val = m.strip()
        if len(val) >= 7:
            phones.add(val)
    # also parse mailto/tel links
    for a in tree.css("a[href]"):
        href = a.attributes.get("href","")
        if href.startswith("mailto:"):
            emails.add(href.split(":",1)[1])
        if href.startswith("tel:"):
            phones.add(href.split(":",1)[1])
    return ContactInfo(emails=sorted(emails), phones=sorted(phones), addresses=[], contact_page=contact_url)

# ---------- Important Links ----------
def extract_important_links(html: str, base: str) -> ImportantLinks:
    tree = HTMLParser(html)
    links = {"order_tracking": None, "contact_us": None, "blogs": None, "sitemap": None, "others": []}
    def match_and_set(a, key, kws):
        href = a.attributes.get("href","")
        text = (a.text() or "").lower()
        for kw in kws:
            if kw in text or kw in href.lower():
                if not links[key]:
                    links[key] = urljoin(base, href)
    for a in tree.css("a[href]"):
        match_and_set(a, "order_tracking", ["track", "order-tracking"])
        match_and_set(a, "contact_us", ["contact"])
        match_and_set(a, "blogs", ["blog", "news", "stories"])
        if "sitemap" in (a.text() or "").lower() or "sitemap.xml" in a.attributes.get("href","").lower():
            links["sitemap"] = urljoin(base, a.attributes.get("href",""))
    # collect other helpful links (returns, size guide)
    others = []
    for a in tree.css("a[href]"):
        href = a.attributes.get("href","")
        txt = (a.text() or "").strip()
        if any(k in href.lower() for k in ["return","size","policy","faq"]):
            others.append(urljoin(base, href))
    links["others"] = list(dict.fromkeys(others))[:20]
    return ImportantLinks(**links)

# ---------- About Text & Brand Name ----------
def extract_about_text(html: str) -> Optional[str]:
    text = trafilatura.extract(html, include_comments=False) or None
    return text

def extract_brand_name_from_ld(html: str, url: str) -> Optional[str]:
    try:
        data = extruct.extract(html, base_url=get_base_url(html, url), syntaxes=["json-ld"], uniform=True)
        for item in data.get("json-ld") or []:
            t = item.get("@type")
            if t in ("Organization","Store","Brand") and item.get("name"):
                return item.get("name")
    except Exception:
        return None
    return None
