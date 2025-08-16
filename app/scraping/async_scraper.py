import httpx, re, asyncio
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
from app.schemas.models import Product
from app.schemas.models import FAQ as FAQModel, SocialHandle as SocialModel, ContactInfo as ContactModel, ImportantLinks as LinksModel
from app.utils import helpers as helpers_mod

class AsyncShopifyScraper:
    def __init__(self, base_url: str, timeout: float = 15.0):
        self.base_url = self._normalize_url(base_url)
        self.client = httpx.AsyncClient(timeout=timeout, follow_redirects=True)
    def _normalize_url(self, url: str) -> str:
        url = url.strip()
        if not url.startswith("http"):
            url = "https://" + url
        return url.rstrip('/')
    async def fetch(self, path: str):
        url = urljoin(self.base_url + "/", path.lstrip('/'))
        try:
            r = await self.client.get(url)
            if r.status_code == 200:
                return r.text
            return None
        except Exception:
            return None
    async def fetch_json(self, path: str):
        url = urljoin(self.base_url + "/", path.lstrip('/'))
        try:
            r = await self.client.get(url)
            if r.status_code == 200:
                return r.json()
            return None
        except Exception:
            return None
    async def close(self):
        await self.client.aclose()
    async def scrape(self):
        # quick health
        home = await self.fetch('/')
        if not home:
            await self.close()
            return None
        # products via /products.json (with collections fallback)
        products_json = await self.fetch_json('/products.json')
        if not products_json:
            products_json = await self.fetch_json('/collections/all/products.json') or {}
        products = []
        for p in (products_json.get('products') or []):
            prod = Product(
                handle=p.get('handle'),
                title=p.get('title'),
                url=urljoin(self.base_url+'/', f"products/{p.get('handle')}") if p.get('handle') else None,
                images=[img.get('src') for img in (p.get('images') or []) if img.get('src')],
                price=float((p.get('variants') or [{}])[0].get('price')) if p.get('variants') else None,
                currency=None,
                sku=[v.get('sku') for v in (p.get('variants') or []) if v.get('sku')],
                tags=(p.get('tags') or '').split(',') if p.get('tags') else [],
                variants=p.get('variants') or [],
                raw=p
            )
            products.append(prod)
        # hero products from home
        hero = self._extract_hero_products(home, products)
        # policies
        privacy = await self.fetch('/policies/privacy-policy') or await self.fetch('/policies/privacy') or await self.fetch('/pages/privacy')
        refund = await self.fetch('/policies/refund-policy') or await self.fetch('/policies/refund') or await self.fetch('/pages/refund')
        returns = await self.fetch('/policies/return-policy') or await self.fetch('/policies/return') or await self.fetch('/pages/return')
        # faqs
        faq_html = await self.fetch('/pages/faqs') or await self.fetch('/pages/faq') or await self.fetch('/pages/help')
        faqs = []
        if faq_html:
            faqs = self._parse_faqs(faq_html)
            faqs = [FAQModel(**f) for f in faqs]
        # socials and contacts
        socials = helpers_mod.extract_socials(home, self.base_url)
        contacts = helpers_mod.extract_contacts(home, self.base_url, None)
        links = helpers_mod.extract_important_links(home, self.base_url)
        # about and brand name
        about = helpers_mod.extract_about_text(home) or None
        brand_name = helpers_mod.extract_brand_name_from_ld(home, self.base_url + '/')
        # seo meta
        seo = self._extract_seo(home)
        # price insights
        price = self._price_insights(products)
        await self.close()
        return {
            'website': self.base_url,
            'brand_name': brand_name,
            'about': about,
            'hero_products': hero,
            'products': products,
            'policies': {'privacy': privacy, 'refund': refund, 'return': returns},
            'faqs': faqs,
            'socials': socials,
            'contacts': contacts,
            'important_links': links,
            'seo': seo,
            'price_insights': price
        }
    def _extract_hero_products(self, home_html, product_objs):
        soup = BeautifulSoup(home_html, 'html.parser')
        hero = []
        handles = {p.handle for p in product_objs if p.handle}
        for a in soup.find_all('a', href=True):
            m = re.match(r"/products/([^/]+)", a['href'])
            if m and m.group(1) in handles:
                hero.append({'handle': m.group(1), 'title': a.get_text(strip=True)})
        # dedupe
        seen = set(); out = []
        for h in hero:
            k = h['handle']
            if k not in seen:
                out.append(h); seen.add(k)
        return out[:12]
    def _parse_faqs(self, html):
        soup = BeautifulSoup(html, 'html.parser')
        faqs = []
        for q in soup.find_all(['h2','h3','strong']):
            question = q.get_text(strip=True)
            nxt = q.find_next_sibling('p')
            answer = nxt.get_text(strip=True) if nxt else ''
            if len(question)>3 and len(answer)>3:
                faqs.append({'question': question, 'answer': answer, 'url': None})
        if not faqs:
            text = soup.get_text('\n', strip=True)
            for m in re.finditer(r'Q[:\)]\s*(.+?)\nA[:\)]\s*(.+?)(?=\nQ[:\)]|\Z)', text, re.DOTALL|re.I):
                faqs.append({'question': m.group(1).strip(), 'answer': m.group(2).strip(), 'url': None})
        return faqs
    def _extract_seo(self, html):
        soup = BeautifulSoup(html, 'html.parser')
        meta = {}
        if soup.title and soup.title.string:
            meta['title'] = soup.title.string.strip()
        desc = soup.find('meta', attrs={'name':'description'}) or soup.find('meta', attrs={'property':'og:description'})
        if desc and desc.get('content'):
            meta['description'] = desc.get('content').strip()
        og = {}
        for tag in soup.find_all('meta'):
            if tag.get('property','').startswith('og:') or tag.get('name','').startswith('twitter:'):
                og_key = tag.get('property') or tag.get('name')
                og[og_key] = tag.get('content')
        meta['og'] = og
        return meta
    def _price_insights(self, products):
        prices = [p.price for p in products if p.price is not None]
        variants = sum(len(p.variants) for p in products)
        if not prices:
            return {}
        avg = sum(prices)/len(prices)
        maxp = max(prices); minp = min(prices)
        # compute discount if variant contains compare_at_price
        discounts = []
        for p in products:
            for v in (p.variants or []):
                try:
                    cp = float(v.get('compare_at_price')) if v.get('compare_at_price') else None
                    price = float(v.get('price')) if v.get('price') else None
                    if cp and price and cp>price:
                        discounts.append(((cp-price)/cp)*100)
                except Exception:
                    continue
        avg_discount = sum(discounts)/len(discounts) if discounts else 0.0
        on_sale = len(discounts)
        return {'average_price': avg, 'min_price': minp, 'max_price': maxp, 'avg_discount_pct': round(avg_discount,2), 'products_on_sale': on_sale, 'total_products': len(products), 'total_variants': variants}
