import asyncio
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import urlparse

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from crawlers.aliexpress import AliexpressCrawler
from crawlers.coupang import CoupangCrawler
from models.product import Product

app = FastAPI(title="Gugu Crawler Server", version="0.3.0")

coupang = CoupangCrawler()
aliexpress = AliexpressCrawler()

executor = ThreadPoolExecutor(max_workers=4)


# --- Models ---

class CrawlRequest(BaseModel):
    url: str


class CrawlResponse(BaseModel):
    success: bool
    data: Product | None = None
    error: str | None = None


# --- Helpers ---

def detect_source(url: str) -> str:
    host = urlparse(url).hostname or ""
    if "coupang.com" in host:
        return "coupang"
    if "aliexpress" in host:
        return "aliexpress"
    raise ValueError(f"Unsupported site: {host}")


def _do_crawl(source: str, url: str) -> Product:
    if source == "coupang":
        return coupang.crawl(url)
    return aliexpress.crawl(url)


# --- Endpoints ---

@app.post("/crawl", response_model=CrawlResponse)
async def crawl_product(req: CrawlRequest):
    try:
        source = detect_source(req.url)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    try:
        loop = asyncio.get_event_loop()
        product = await loop.run_in_executor(executor, _do_crawl, source, req.url)
        return CrawlResponse(success=True, data=product)
    except Exception as e:
        return CrawlResponse(success=False, error=str(e))


@app.get("/health")
def health():
    return {"status": "ok"}
