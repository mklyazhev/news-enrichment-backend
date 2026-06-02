from fastapi import FastAPI

from src.api.enrichment import router as enrichment_router
from src.api.news import router as news_router

app = FastAPI()
app.include_router(news_router, prefix="/api/v1")
app.include_router(enrichment_router, prefix="/api/v1")


@app.get("/ping")
def ping() -> dict[str, str]:
    return {"status": "ok"}
