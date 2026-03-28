import re
import json
import time

from playwright.sync_api import sync_playwright, Page

from models.product import Product, SkuPrice

CURRENCY_SYMBOL_MAP = {
    "₩": "KRW",
    "$": "USD",
    "€": "EUR",
    "¥": "CNY",
    "£": "GBP",
}


def _extract_currency_and_number(text: str) -> tuple[str, str]:
    """'₩1,217' -> ('KRW', '1217')"""
    if not text:
        return ("", "")
    match = re.search(r"([₩$€¥£])\s?([\d,]+\.?\d*)", text)
    if match:
        symbol = match.group(1)
        number = match.group(2).replace(",", "")
        currency = CURRENCY_SYMBOL_MAP.get(symbol, symbol)
        return (currency, number)
    number = re.sub(r"[^\d.]", "", text)
    return ("", number)


class AliexpressCrawler:
    SOURCE = "aliexpress"

    def crawl(self, url: str) -> Product:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            sku_payloads: list[dict] = []

            def handle_response(response):
                if "mtop.aliexpress.pdp.pc.query" not in response.url:
                    return
                try:
                    body = response.text()
                except Exception:
                    return
                payload = self._parse_jsonp_payload(body)
                if not payload:
                    return
                ret = "".join(payload.get("ret") or [])
                if "SUCCESS" in ret:
                    sku_payloads.append(payload)

            page.on("response", handle_response)
            page.goto(url, wait_until="load", timeout=30000)
            page.wait_for_timeout(5000)

            self._close_popups(page)
            title = self._parse_title(page)
            main_image = self._parse_main_image(page)
            images = self._parse_images(page)

            browser.close()

        if not sku_payloads:
            raise ValueError("AliExpress prefetch response not found")

        payload = sku_payloads[-1]
        skus = self._extract_skus_from_payload(payload)

        payload_images = self._extract_images_from_payload(payload)
        if not main_image and payload_images:
            main_image = payload_images[0]
        if not images:
            images = payload_images

        return Product(
            title=title,
            url=url,
            source=self.SOURCE,
            skus=skus,
            main_image=main_image,
            images=images,
        )

    # --- Page parsing (DOM) ---

    def _close_popups(self, page: Page):
        page.evaluate('''() => {
            document.querySelectorAll(
                '[class*="cosmos-drawer"], [class*="popup"], [class*="modal"], '
                + '[class*="overlay"], [class*="mask"]'
            ).forEach(el => el.remove());
        }''')
        time.sleep(0.3)

    def _parse_title(self, page: Page) -> str:
        el = page.locator('h1, [data-pl="product-title"]').first
        try:
            return el.inner_text(timeout=5000).strip()
        except Exception:
            return ""

    def _parse_main_image(self, page: Page) -> str | None:
        el = page.locator('meta[property="og:image"]')
        if el.count() > 0:
            return el.first.get_attribute("content")
        img = page.locator('[class*="slider--img"] img, [class*="gallery"] img').first
        try:
            return img.get_attribute("src", timeout=3000)
        except Exception:
            return None

    def _parse_images(self, page: Page) -> list[str]:
        try:
            result = page.evaluate('''() => {
                const data = window._d_c_ && window._d_c_.DCData;
                if (data && data.imagePathList) return data.imagePathList;
                const imgs = document.querySelectorAll('[class*="slider--img"] img, [class*="gallery"] img');
                return [...imgs].map(i => i.src).filter(Boolean);
            }''')
            return result or []
        except Exception:
            return []

    # --- JSONP parsing ---

    def _parse_jsonp_payload(self, body: str) -> dict | None:
        match = re.search(r"mtopjsonp\d+\((.*)\)\s*$", body, re.S)
        if not match:
            return None
        try:
            return json.loads(match.group(1))
        except json.JSONDecodeError:
            return None

    # --- Payload extraction ---

    def _extract_skus_from_payload(self, payload: dict) -> list[SkuPrice]:
        result = payload.get("data", {}).get("result", {})
        sku_data = result.get("SKU", {})
        sku_paths = sku_data.get("skuPaths") or []
        sku_properties = sku_data.get("skuProperties") or []

        property_lookup = self._build_sku_property_lookup(sku_properties)
        image_lookup = self._build_sku_image_lookup(sku_properties)
        price_lookup = self._build_sku_price_lookup(sku_data, result)

        skus: list[SkuPrice] = []

        for sku_path in sku_paths:
            sku_id = str(sku_path.get("skuIdStr") or sku_path.get("skuId") or "").strip()
            sku_attr = sku_path.get("skuAttr") or ""
            if not sku_id:
                continue

            sku_name = self._build_sku_name_from_attr(sku_attr, property_lookup)
            color, size = self._parse_color_size(sku_name)
            image_url = self._resolve_sku_image(sku_attr, image_lookup)

            price_info = price_lookup.get(sku_id, {})
            currency = price_info.get("currency", "")
            price = price_info.get("price", "")
            original_price = price_info.get("original_price")

            skus.append(SkuPrice(
                external_sku_id=sku_id,
                sku_name=sku_name,
                color=color,
                size=size,
                price=price,
                original_price=original_price,
                currency=currency,
                image_url=image_url,
            ))

        return skus

    def _build_sku_property_lookup(self, sku_properties: list[dict]) -> dict[str, str]:
        lookup: dict[str, str] = {}
        for prop in sku_properties:
            pid = str(prop.get("skuPropertyId"))
            for val in prop.get("skuPropertyValues") or []:
                vid = str(val.get("propertyValueIdLong"))
                label = (
                    val.get("propertyValueDisplayName")
                    or val.get("propertyValueName")
                    or val.get("propertyValueDefinitionName")
                    or vid
                )
                lookup[f"{pid}:{vid}"] = label
        return lookup

    def _build_sku_image_lookup(self, sku_properties: list[dict]) -> dict[str, str]:
        """Build valueId -> image_url mapping from skuProperties."""
        lookup: dict[str, str] = {}
        for prop in sku_properties:
            pid = str(prop.get("skuPropertyId"))
            for val in prop.get("skuPropertyValues") or []:
                vid = str(val.get("propertyValueIdLong"))
                img = (
                    val.get("skuPropertyImagePath")
                    or val.get("skuPropertyImageSummPath")
                    or val.get("skuPropertyTips")
                )
                if img and img.startswith(("http", "//")):
                    if img.startswith("//"):
                        img = "https:" + img
                    lookup[f"{pid}:{vid}"] = img
        return lookup

    def _build_sku_price_lookup(self, sku_data: dict, result: dict) -> dict[str, dict]:
        """Build skuId -> {price, original_price, currency} from PRICE.skuPriceInfoMap."""
        lookup: dict[str, dict] = {}

        price_section = result.get("PRICE", {})
        price_map = price_section.get("skuPriceInfoMap") or price_section.get("skuIdStrPriceInfoMap") or {}

        for sku_id, info in price_map.items():
            original = info.get("originalPrice") or {}
            currency = original.get("currency", "")
            orig_value = original.get("value")

            # salePriceLocal format: "₩10,028|10028|"
            sale_price_local = info.get("salePriceLocal") or ""
            parts = sale_price_local.split("|")
            sale_value = parts[1] if len(parts) >= 2 and parts[1] else None

            # Fallback: parse from salePriceString "₩10,028"
            if not sale_value:
                _, sale_value = _extract_currency_and_number(info.get("salePriceString") or "")

            price_str = sale_value or ""
            orig_str = None
            if orig_value is not None:
                orig_str = str(int(orig_value)) if isinstance(orig_value, float) else str(orig_value)
                if orig_str == price_str:
                    orig_str = None

            if not currency and sale_price_local:
                c, _ = _extract_currency_and_number(sale_price_local.split("|")[0])
                currency = c

            lookup[sku_id] = {
                "price": price_str,
                "original_price": orig_str,
                "currency": currency,
            }

        return lookup

    def _extract_images_from_payload(self, payload: dict) -> list[str]:
        """Extract product images from payload."""
        result = payload.get("data", {}).get("result", {})

        # Try imageModule
        image_module = result.get("imageModule") or {}
        images = image_module.get("imagePathList") or []
        if images:
            return [self._normalize_url(img) for img in images if img]

        # Try top-level imagePathList
        images = result.get("imagePathList") or []
        if images:
            return [self._normalize_url(img) for img in images if img]

        return []

    def _normalize_url(self, url: str) -> str:
        if url.startswith("//"):
            return "https:" + url
        return url

    def _build_sku_name_from_attr(self, sku_attr: str, property_lookup: dict[str, str]) -> str:
        labels = []
        for raw_part in sku_attr.split(";"):
            part = raw_part.split("#", 1)[0].strip()
            if not part:
                continue
            labels.append(property_lookup.get(part, raw_part.strip()))
        return " / ".join(labels)

    def _parse_color_size(self, sku_name: str) -> tuple[str | None, str | None]:
        if " / " in sku_name:
            parts = sku_name.split(" / ", 1)
            return parts[0], parts[1]
        if sku_name and sku_name != "default":
            return sku_name, None
        return None, None

    def _resolve_sku_image(self, sku_attr: str, image_lookup: dict[str, str]) -> str | None:
        """Find image for a SKU by checking its attribute values against image lookup."""
        for raw_part in sku_attr.split(";"):
            key = raw_part.split("#", 1)[0].strip()
            if key in image_lookup:
                return image_lookup[key]
        return None
