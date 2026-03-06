import requests
from bs4 import BeautifulSoup

from models.product import Product
from utils.headers import get_headers


class BaseCrawler:
    SOURCE = ""
    LANG = "ko"

    def fetch(self, url: str) -> BeautifulSoup:
        response = requests.get(url, headers=get_headers(self.LANG), timeout=15)
        response.raise_for_status()
        return BeautifulSoup(response.text, "lxml")

    def crawl(self, url: str) -> Product:
        raise NotImplementedError
