# Gugu Crawler Server

Coupang, AliExpress 상품 정보를 크롤링하는 FastAPI 서버.

## 설치 및 실행

```bash
# 가상환경 생성 및 활성화
python -m venv venv
source venv/bin/activate

# 패키지 설치
pip install -r requirements.txt

# Playwright 브라우저 설치
playwright install chromium

# 서버 실행
uvicorn app:app --reload --port 8000
```

## API

### POST /crawl

상품 URL을 받아 크롤링 결과를 반환한다.

```bash
curl -X POST http://localhost:8000/crawl \
  -H "Content-Type: application/json" \
  -d '{"url": "https://www.coupang.com/vp/products/..."}'
```

```json
{
  "success": true,
  "data": {
    "title": "상품명",
    "url": "https://...",
    "source": "coupang",
    "skus": [
      {
        "sku_name": "옵션명",
        "price": "12,900",
        "original_price": "15,900",
        "image": "https://..."
      }
    ],
    "main_image": "https://...",
    "images": []
  },
  "error": null
}
```

### GET /health

```bash
curl http://localhost:8000/health
# {"status": "ok"}
```

## 지원 사이트

| 사이트 | 크롤러 |
|--------|--------|
| Coupang | `crawlers/coupang.py` |
| AliExpress | `crawlers/aliexpress.py` |

## 구조

```
├── app.py              # FastAPI 엔트리포인트
├── crawlers/           # 사이트별 크롤러
├── models/             # Pydantic 모델
├── utils/              # 유틸리티
└── docs/               # 아키텍처 문서
```
