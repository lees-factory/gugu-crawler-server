import re
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
    # fallback: just strip non-digits
    number = re.sub(r"[^\d.]", "", text)
    return ("", number)


class AliexpressCrawler:
    SOURCE = "aliexpress"

    def crawl(self, url: str) -> Product:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            page.goto(url, wait_until="networkidle", timeout=30000)

            self._close_popups(page)

            title = self._parse_title(page)
            main_image = self._parse_main_image(page)
            images = self._parse_images(page)
            skus = self._parse_skus(page)

            browser.close()

        return Product(
            title=title,
            url=url,
            source=self.SOURCE,
            skus=skus,
            main_image=main_image,
            images=images,
        )

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

    def _get_price(self, page: Page) -> tuple[str, str | None]:
        """Returns (current_price, original_price) as raw strings like '₩1,217'."""
        try:
            result = page.evaluate('''() => {
                const currentEl = document.querySelector('[class*="--current--"]');
                const current = currentEl ? currentEl.textContent.trim() : "";
                const originEl = document.querySelector('[class*="--originWrap--"], [class*="--origin--"], [class*="--del--"]');
                const origin = originEl ? originEl.textContent.trim() : null;
                return {current, origin};
            }''')
        except Exception:
            return ("", None)

        current = result.get("current", "")
        origin = result.get("origin")

        def extract_price(text):
            if not text:
                return None
            match = re.search(r"[₩$€¥£]\s?[\d,]+\.?\d*", text)
            if match:
                return match.group(0)
            lines = [l.strip() for l in text.split("\n") if l.strip()]
            prices = [l for l in lines if re.search(r"[\d₩$€¥£]", l)]
            return prices[0] if prices else text

        return (extract_price(current) or "", extract_price(origin))

    def _to_sku_price(self, sku_name: str, raw_price: str, raw_original: str | None, image: str | None) -> SkuPrice:
        """Convert raw scraped data to unified SkuPrice format per mapping rules."""
        # Split color / size from sku_name
        color = None
        size = None
        if " / " in sku_name:
            parts = sku_name.split(" / ", 1)
            color = parts[0]
            size = parts[1]
        elif sku_name != "default":
            color = sku_name

        # Extract currency and numeric price
        currency_p, price_num = _extract_currency_and_number(raw_price)
        currency_o, original_num = _extract_currency_and_number(raw_original or "")
        currency = currency_p or currency_o or ""

        return SkuPrice(
            external_sku_id=sku_name,
            sku_name=sku_name,
            color=color,
            size=size,
            price=price_num,
            original_price=original_num or None,
            currency=currency,
            image_url=image,
            sku_properties="",
        )

    def _parse_skus(self, page: Page) -> list[SkuPrice]:
        color_items = page.locator('[class*="sku-item--image"]')
        size_items = page.locator('[class*="sku-item--text"]')
        color_count = color_items.count()
        size_count = size_items.count()

        skus = []

        if color_count == 0 and size_count == 0:
            price, original = self._get_price(page)
            skus.append(self._to_sku_price("default", price, original, None))
            return skus

        colors = []
        for i in range(color_count):
            item = color_items.nth(i)
            name = item.get_attribute("title") or ""
            if not name:
                img = item.locator("img").first
                name = img.get_attribute("alt") or f"color_{i}"
            img_el = item.locator("img").first
            img_src = img_el.get_attribute("src") if img_el.count() > 0 else None
            colors.append({"name": name, "image": img_src, "index": i})

        sizes = []
        for i in range(size_count):
            item = size_items.nth(i)
            name = item.get_attribute("title") or item.inner_text().strip()
            sizes.append({"name": name, "index": i})

        if colors and sizes:
            # Color당 1개 SKU (첫 번째 size 기준) - Affiliate API 동일 동작
            first_size = sizes[0]
            size_items.nth(first_size["index"]).click(force=True)
            time.sleep(0.2)

            for color in colors:
                color_items.nth(color["index"]).click(force=True)
                time.sleep(0.2)
                price, original = self._get_price(page)
                sku_name = f"{color['name']} / {first_size['name']}"
                skus.append(self._to_sku_price(sku_name, price, original, color.get("image")))
        elif colors:
            for color in colors:
                color_items.nth(color["index"]).click(force=True)
                time.sleep(0.3)
                price, original = self._get_price(page)
                skus.append(self._to_sku_price(color["name"], price, original, color.get("image")))
        elif sizes:
            for size in sizes:
                size_items.nth(size["index"]).click(force=True)
                time.sleep(0.3)
                price, original = self._get_price(page)
                skus.append(self._to_sku_price(size["name"], price, original, None))

        return skus
