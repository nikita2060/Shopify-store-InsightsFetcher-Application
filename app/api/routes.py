
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, HttpUrl
from typing import Optional
from app.schemas.models import BrandContext, ErrorResponse
from app.services.insights_service import gather_insights, gather_insights_and_persist, competitor_insights
router = APIRouter()
class InsightsRequest(BaseModel):
    website_url: HttpUrl
@router.post("/insights", response_model=BrandContext, responses={401: {"model": ErrorResponse}, 500: {"model": ErrorResponse}})
async def insights(req: InsightsRequest, persist: Optional[bool] = Query(False, description="Persist results to DB"), mode: Optional[str] = Query('full', description='fast uses lightweight fetch, full uses async scraper')):
    try:
        if persist:
            result = await gather_insights_and_persist(str(req.website_url))
        else:
            result = await gather_insights(str(req.website_url))
        if result is None:
            raise HTTPException(status_code=401, detail="Website not found or not a Shopify storefront")
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal error: {e}")
@router.post('/competitors', response_model=dict)
async def competitors(req: InsightsRequest, limit: Optional[int] = Query(3, ge=1, le=10)):
    try:
        data = await competitor_insights(str(req.website_url), limit=limit)
        return data
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal error: {e}")
