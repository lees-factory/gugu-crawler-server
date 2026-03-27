import asyncio
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import urlparse

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from crawlers.aliexpress import AliexpressCrawler
from crawlers.coupang import CoupangCrawler
from models.product import AliexpressSkuIdResult, Product

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


class AliexpressSkuIdsResponse(BaseModel):
    success: bool
    data: AliexpressSkuIdResult | None = None
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


def _do_crawl_aliexpress_sku_ids(url: str) -> AliexpressSkuIdResult:
    return aliexpress.crawl_sku_ids(url)


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


@app.post("/aliexpress/sku-ids", response_model=AliexpressSkuIdsResponse)
async def crawl_aliexpress_sku_ids(req: CrawlRequest):
    try:
        source = detect_source(req.url)
        if source != "aliexpress":
            raise HTTPException(status_code=400, detail="AliExpress URL only")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    try:
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(executor, _do_crawl_aliexpress_sku_ids, req.url)
        return AliexpressSkuIdsResponse(success=True, data=result)
    except Exception as e:
        return AliexpressSkuIdsResponse(success=False, error=str(e))


@app.get("/health")
def health():
    return {"status": "ok"}
