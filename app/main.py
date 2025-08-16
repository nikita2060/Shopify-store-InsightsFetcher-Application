from fastapi import FastAPI
from app.api.routes import router

app = FastAPI(title="Shopify Insights-Fetcher", version="1.0.0")
app.include_router(router)

@app.get("/healthz")
async def health():
    return {"status": "ok"}
