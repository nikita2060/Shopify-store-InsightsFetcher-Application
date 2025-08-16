from app.schemas.models import BrandContext

def test_brand_context_fields():
    model = BrandContext.model_fields
    assert "website" in model and "product_catalog" in model
