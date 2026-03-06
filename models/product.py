from pydantic import BaseModel


class SkuPrice(BaseModel):
    sku_name: str
    price: str
    original_price: str | None = None
    image: str | None = None


class Product(BaseModel):
    title: str
    url: str
    source: str  # "coupang" or "aliexpress"
    skus: list[SkuPrice]
    main_image: str | None = None
    images: list[str] = []
