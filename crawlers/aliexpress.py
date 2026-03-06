import re
import time

from playwright.sync_api import sync_playwright, Page

from models.product import Product, SkuPrice


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
        """Returns (current_price, original_price)."""
        try:
            result = page.evaluate('''() => {
                // Current price: span with class like "price-kr--current--xxx"
                const currentEl = document.querySelector('[class*="--current--"]');
                const current = currentEl ? currentEl.textContent.trim() : "";

                // Original price: div with class like "price-kr--originWrap--xxx"
                const originEl = document.querySelector('[class*="--originWrap--"], [class*="--origin--"], [class*="--del--"]');
                const origin = originEl ? originEl.textContent.trim() : null;

                return {current, origin};
            }''')
        except Exception:
            return ("", None)

        current = result.get("current", "")
        origin = result.get("origin")

        # Extract price strings (lines with currency/digits)
        def extract_price(text):
            if not text:
                return None
            # Extract only the currency + number part (e.g. "₩1,217" from "원가 ₩1,217")
            match = re.search(r"[₩$€¥£]\s?[\d,]+\.?\d*", text)
            if match:
                return match.group(0)
            lines = [l.strip() for l in text.split("\n") if l.strip()]
            prices = [l for l in lines if re.search(r"[\d₩$€¥£]", l)]
            return prices[0] if prices else text

        return (extract_price(current) or "", extract_price(origin))

    def _parse_skus(self, page: Page) -> list[SkuPrice]:
        color_items = page.locator('[class*="sku-item--image"]')
        size_items = page.locator('[class*="sku-item--text"]')
        color_count = color_items.count()
        size_count = size_items.count()

        skus = []

        if color_count == 0 and size_count == 0:
            price, original = self._get_price(page)
            skus.append(SkuPrice(sku_name="default", price=price, original_price=original))
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
            # Step 1: click first color, iterate all sizes to get base prices
            color_items.nth(colors[0]["index"]).click(force=True)
            time.sleep(0.2)
            base_prices = {}
            for size in sizes:
                size_items.nth(size["index"]).click(force=True)
                time.sleep(0.2)
                price, original = self._get_price(page)
                base_prices[size["name"]] = (price, original)
                skus.append(SkuPrice(
                    sku_name=f"{colors[0]['name']} / {size['name']}",
                    price=price,
                    original_price=original,
                    image=colors[0].get("image"),
                ))

            # Step 2: for other colors, click color + first size to check price
            for color in colors[1:]:
                color_items.nth(color["index"]).click(force=True)
                time.sleep(0.2)
                size_items.nth(sizes[0]["index"]).click(force=True)
                time.sleep(0.2)
                check_price, check_original = self._get_price(page)

                if check_price == base_prices[sizes[0]["name"]][0]:
                    # Same price as first color → reuse base prices
                    for size in sizes:
                        bp, bo = base_prices[size["name"]]
                        skus.append(SkuPrice(
                            sku_name=f"{color['name']} / {size['name']}",
                            price=bp,
                            original_price=bo,
                            image=color.get("image"),
                        ))
                else:
                    # Different price → iterate all sizes for this color
                    skus.append(SkuPrice(
                        sku_name=f"{color['name']} / {sizes[0]['name']}",
                        price=check_price,
                        original_price=check_original,
                        image=color.get("image"),
                    ))
                    for size in sizes[1:]:
                        size_items.nth(size["index"]).click(force=True)
                        time.sleep(0.2)
                        price, original = self._get_price(page)
                        skus.append(SkuPrice(
                            sku_name=f"{color['name']} / {size['name']}",
                            price=price,
                            original_price=original,
                            image=color.get("image"),
                        ))
        elif colors:
            for color in colors:
                color_items.nth(color["index"]).click(force=True)
                time.sleep(0.3)
                price, original = self._get_price(page)
                skus.append(SkuPrice(
                    sku_name=color["name"],
                    price=price,
                    original_price=original,
                    image=color.get("image"),
                ))
        elif sizes:
            for size in sizes:
                size_items.nth(size["index"]).click(force=True)
                time.sleep(0.3)
                price, original = self._get_price(page)
                skus.append(SkuPrice(
                    sku_name=size["name"],
                    price=price,
                    original_price=original,
                ))

        return skus
