# Gugu Crawler Server

Coupang, AliExpress 상품 정보를 크롤링하는 FastAPI 서버.

## 설치

```bash
# 가상환경 생성 및 활성화
python -m venv venv
source venv/bin/activate

# 패키지 설치
pip install -r requirements.txt

# Playwright 브라우저 설치
playwright install chromium

```

## 실행 방법

### 기본 실행

```bash
uvicorn app:app --reload --host 0.0.0.0 --port 8000
```

- 기본 포트는 `8000`이다.
- 로컬에서 확인할 때는 `http://localhost:8000`으로 접근하면 된다.

### 포트 번호 변경

다른 포트로 실행하려면 `--port` 값을 바꾸면 된다.

```bash
uvicorn app:app --reload --host 0.0.0.0 --port 8080
```

- 예를 들어 `8080`으로 실행했다면 API 호출 주소도 `http://localhost:8080`으로 변경해야 한다.

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
