
from selectolax.parser import HTMLParser
import re
from urllib.parse import urljoin

EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
PHONE_RE = re.compile(r"(?:\+\d{1,3}[-.\s]?)?(?:\(?\d{2,4}\)?[-.\s]?)?\d{3,4}[-.\s]?\d{3,4}")

def extract_emails(html):
    return list(set(EMAIL_RE.findall(html or "")))

def extract_phones(html):
    phones = set()
    for m in PHONE_RE.findall(html or ""):
        val = m.strip()
        if len(val)>=7:
            phones.add(val)
    return list(phones)

def extract_socials(html, base):
    tree = HTMLParser(html or "")
    found = []
    SOCIAL_DOMAINS = {"instagram":"instagram.com","facebook":"facebook.com","tiktok":"tiktok.com","x":"x.com","twitter":"twitter.com","youtube":"youtube.com","pinterest":"pinterest.com","linkedin":"linkedin.com"}
    for a in tree.css('a[href]'):
        href = a.attributes.get('href','')
        for platform, domain in SOCIAL_DOMAINS.items():
            if domain in href:
                handle = href.split('/')[-1].strip('/')
                found.append({'platform': platform, 'url': href, 'handle': handle})
    # dedupe by platform
    out=[]; seen=set()
    for s in found:
        if s['platform'] not in seen:
            out.append(s); seen.add(s['platform'])
    return out

def extract_social_links(html):
    return extract_socials(html, None)

def extract_contacts(html, base, contact_url):
    tree = HTMLParser(html or "")
    emails = extract_emails(html)
    phones = extract_phones(html)
    return {'emails': emails, 'phones': phones, 'addresses': [], 'contact_page': contact_url}

def extract_important_links(html, base):
    tree = HTMLParser(html or "")
    links = {'order_tracking': None, 'contact_us': None, 'blogs': None, 'sitemap': None, 'others': []}
    for a in tree.css('a[href]'):
        href = a.attributes.get('href','')
        text = (a.text() or '').lower()
        if 'track' in text or 'order' in href:
            links['order_tracking'] = urljoin(base+'/', href)
        if 'contact' in text or 'support' in text:
            links['contact_us'] = urljoin(base+'/', href)
        if 'blog' in text:
            links['blogs'] = urljoin(base+'/', href)
        if 'sitemap' in href or 'sitemap' in text:
            links['sitemap'] = urljoin(base+'/', href)
    return links

def extract_about_text(html):
    # try to pull main text heuristically
    tree = HTMLParser(html or "")
    body = tree.body.text() if tree.body else ''
    return body.strip()[:3000]

def extract_brand_name_from_ld(html, url):
    # simple heuristic: title or meta og:site_name
    tree = HTMLParser(html or "")
    title = tree.css_first('title')
    if title:
        return title.text()
    og = tree.css_first('meta[property="og:site_name"]')
    if og:
        return og.attributes.get('content')
    return None
