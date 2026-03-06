import json
import re

from bs4 import BeautifulSoup

from crawlers.base import BaseCrawler
from models.product import Product, SkuPrice


class CoupangCrawler(BaseCrawler):
    SOURCE = "coupang"
    LANG = "ko"

    def crawl(self, url: str) -> Product:
        soup = self.fetch(url)

        title = self._parse_title(soup)
        main_image = self._parse_main_image(soup)
        images = self._parse_images(soup)
        skus = self._parse_skus(soup)

        return Product(
            title=title,
            url=url,
            source=self.SOURCE,
            skus=skus,
            main_image=main_image,
            images=images,
        )

    def _parse_title(self, soup: BeautifulSoup) -> str:
        el = soup.select_one("h1.prod-buy-header__title, h2.prod-buy-header__title")
        if el:
            return el.get_text(strip=True)
        meta = soup.select_one("meta[property='og:title']")
        if meta:
            return meta.get("content", "")
        return ""

    def _parse_main_image(self, soup: BeautifulSoup) -> str | None:
        el = soup.select_one("img.prod-image__detail")
        if el:
            src = el.get("src") or el.get("data-img-src", "")
            return self._normalize_url(src)
        meta = soup.select_one("meta[property='og:image']")
        if meta:
            return meta.get("content")
        return None

    def _parse_images(self, soup: BeautifulSoup) -> list[str]:
        images = []
        for el in soup.select("img.prod-image__detail, ul.prod-image__list img"):
            src = el.get("src") or el.get("data-img-src", "")
            normalized = self._normalize_url(src)
            if normalized and normalized not in images:
                images.append(normalized)
        return images

    def _parse_skus(self, soup: BeautifulSoup) -> list[SkuPrice]:
        skus = []

        # Try to extract from embedded JSON (sdp.bundle script)
        skus = self._parse_skus_from_script(soup)
        if skus:
            return skus

        # Fallback: parse option selectors + visible price
        skus = self._parse_skus_from_html(soup)
        return skus

    def _parse_skus_from_script(self, soup: BeautifulSoup) -> list[SkuPrice]:
        """Extract SKU data from inline JavaScript/JSON in the page."""
        skus = []
        for script in soup.select("script"):
            text = script.string or ""
            # Look for vendorItemMap or similar JSON structures
            match = re.search(r"vendorItemMap\s*=\s*(\{.*?\});", text, re.DOTALL)
            if not match:
                match = re.search(r'"options"\s*:\s*(\[.*?\])', text, re.DOTALL)
            if match:
                try:
                    data = json.loads(match.group(1))
                    if isinstance(data, dict):
                        for key, item in data.items():
                            skus.append(SkuPrice(
                                sku_name=item.get("itemName", key),
                                price=str(item.get("salesPrice", item.get("price", ""))),
                                original_price=str(item.get("basePrice", "")) or None,
                                image=item.get("image"),
                            ))
                    elif isinstance(data, list):
                        for item in data:
                            skus.append(SkuPrice(
                                sku_name=item.get("name", item.get("label", "")),
                                price=str(item.get("price", "")),
                                original_price=str(item.get("originalPrice", "")) or None,
                                image=item.get("image"),
                            ))
                except (json.JSONDecodeError, AttributeError):
                    continue
        return skus

    def _parse_skus_from_html(self, soup: BeautifulSoup) -> list[SkuPrice]:
        """Fallback: parse price from HTML when no script data available."""
        skus = []
        price_el = soup.select_one("span.total-price strong")
        price = price_el.get_text(strip=True) if price_el else ""

        original_el = soup.select_one("span.origin-price")
        original_price = original_el.get_text(strip=True) if original_el else None

        # Check for option buttons/selectors
        option_items = soup.select("ul.prod-option__item li button, div.prod-option button")
        if option_items:
            for btn in option_items:
                name = btn.get_text(strip=True)
                if name:
                    skus.append(SkuPrice(
                        sku_name=name,
                        price=price,
                        original_price=original_price,
                    ))
        else:
            # Single SKU product
            skus.append(SkuPrice(
                sku_name="default",
                price=price,
                original_price=original_price,
            ))

        return skus

    def _normalize_url(self, url: str) -> str:
        if not url:
            return ""
        url = url.strip()
        if url.startswith("//"):
            return "https:" + url
        return url
