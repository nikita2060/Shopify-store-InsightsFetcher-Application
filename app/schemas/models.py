from pydantic import BaseModel, HttpUrl, EmailStr, Field
from typing import Literal, Optional, List, Dict, Any
from datetime import datetime

class Product(BaseModel):
    handle: Optional[str] = None
    title: Optional[str] = None
    url: Optional[HttpUrl] = None
    images: List[HttpUrl] = []
    price: Optional[float] = None
    currency: Optional[str] = None
    sku: List[str] = []
    tags: List[str] = []
    variants: List[Dict[str, Any]] = []
    raw: Optional[Dict[str, Any]] = None

class Policy(BaseModel):
    type: Literal["privacy", "refund", "return", "shipping", "terms", "faq", "warranty", "payment"]
    url: HttpUrl
    content_html: Optional[str] = None
    content_text: Optional[str] = None

class FAQ(BaseModel):
    question: str
    answer: str
    url: Optional[HttpUrl] = None

class SocialHandle(BaseModel):
    platform: Literal["instagram","facebook","tiktok","x","twitter","youtube","pinterest","linkedin"]
    url: HttpUrl
    handle: Optional[str] = None

class ContactInfo(BaseModel):
    emails: List[EmailStr] = []
    phones: List[str] = []
    addresses: List[str] = []
    contact_page: Optional[HttpUrl] = None

class ImportantLinks(BaseModel):
    order_tracking: Optional[HttpUrl] = None
    contact_us: Optional[HttpUrl] = None
    blogs: Optional[HttpUrl] = None
    sitemap: Optional[HttpUrl] = None
    others: List[HttpUrl] = []

class BrandContext(BaseModel):
    website: HttpUrl
    brand_name: Optional[str] = None
    about_text: Optional[str] = None
    hero_products: List[Product] = []
    product_catalog: List[Product] = []
    policies: List[Policy] = []
    faqs: List[FAQ] = []
    socials: List[SocialHandle] = []
    contacts: ContactInfo = Field(default_factory=ContactInfo)
    important_links: ImportantLinks = Field(default_factory=ImportantLinks)
    fetched_at: datetime
    meta: Dict[str, Any] = {}

class ErrorResponse(BaseModel):
    detail: str
    code: Optional[str] = None
