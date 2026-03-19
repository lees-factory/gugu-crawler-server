from pydantic import BaseModel


class SkuPrice(BaseModel):
    external_sku_id: str
    sku_name: str
    color: str | None = None
    size: str | None = None
    price: str
    original_price: str | None = None
    currency: str
    image_url: str | None = None
    sku_properties: str = ""


class Product(BaseModel):
    title: str
    url: str
    source: str  # "coupang" or "aliexpress"
    skus: list[SkuPrice]
    main_image: str | None = None
    images: list[str] = []
