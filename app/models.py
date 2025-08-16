from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, JSON
from sqlalchemy.orm import relationship
from datetime import datetime
from app.db import Base
class Brand(Base):
    __tablename__ = "brands"
    id = Column(Integer, primary_key=True, index=True)
    domain = Column(String(255), unique=True, index=True, nullable=False)
    name = Column(String(255))
    about_text = Column(Text)
    fetched_at = Column(DateTime, default=datetime.utcnow)
    meta = Column(JSON, default={})
    products = relationship("Product", back_populates="brand", cascade="delete")
    policies = relationship("Policy", back_populates="brand", cascade="delete")
    faqs = relationship("FAQ", back_populates="brand", cascade="delete")
    socials = relationship("Social", back_populates="brand", cascade="delete")
class Product(Base):
    __tablename__ = "products"
    id = Column(Integer, primary_key=True, index=True)
    brand_id = Column(Integer, ForeignKey("brands.id"))
    handle = Column(String(255), index=True)
    title = Column(String(512))
    url = Column(String(1024))
    images = Column(JSON)
    price = Column(String(64))
    currency = Column(String(16))
    sku = Column(JSON)
    tags = Column(JSON)
    variants = Column(JSON)
    raw = Column(JSON)
    brand = relationship("Brand", back_populates="products")
class Policy(Base):
    __tablename__ = "policies"
    id = Column(Integer, primary_key=True, index=True)
    brand_id = Column(Integer, ForeignKey("brands.id"))
    type = Column(String(64))
    url = Column(String(1024))
    content_text = Column(Text)
    content_html = Column(Text)
    brand = relationship("Brand", back_populates="policies")
class FAQ(Base):
    __tablename__ = "faqs"
    id = Column(Integer, primary_key=True, index=True)
    brand_id = Column(Integer, ForeignKey("brands.id"))
    question = Column(Text)
    answer = Column(Text)
    url = Column(String(1024))
    brand = relationship("Brand", back_populates="faqs")
class Social(Base):
    __tablename__ = "socials"
    id = Column(Integer, primary_key=True, index=True)
    brand_id = Column(Integer, ForeignKey("brands.id"))
    platform = Column(String(64))
    url = Column(String(1024))
    handle = Column(String(255))
    brand = relationship("Brand", back_populates="socials")
