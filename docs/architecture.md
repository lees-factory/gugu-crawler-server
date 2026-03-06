# Gugu System Architecture

## 전체 시스템 구성

```
┌─────────────────┐       ┌──────────────────┐       ┌───────────┐
│   Gugu Client   │──────▶│   Main Server    │──────▶│  Supabase │
│   (Mobile App)  │◀──────│   (NestJS/etc)   │◀──────│    DB     │
└─────────────────┘       └───────┬──────────┘       └───────────┘
                                  │
                          fallback│크롤링 요청
                                  ▼
                          ┌──────────────────┐
                          │  Crawler Server  │
                          │  (FastAPI/Python) │
                          └──────────────────┘
```

## 서버별 역할

### Main Server (메인 서버)
- **유저 관리**: 회원가입, 로그인, 인증 (Supabase Auth)
- **상품 관리**: 유저별 상품 등록/조회/삭제
- **배치 프로세스**: 주기적 가격 갱신 (Affiliate API → fallback → Crawler Server)
- **가격 이력**: 가격 변동 추적 및 알림
- **기술 스택**: NestJS or FastAPI, Supabase 연동

### Crawler Server (크롤링 서버) - 이 레포지토리
- **역할**: 순수 크롤링 전용 서버 (stateless)
- **인증**: 없음 (내부 서비스 간 통신 전용, 네트워크 레벨 보안)
- **DB**: 없음 (데이터 저장은 메인 서버가 담당)
- **기술 스택**: FastAPI, Playwright (headless browser)

#### API 스펙

**POST /crawl**
- Request: `{ "url": "https://www.coupang.com/..." }`
- Response:
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
    "images": ["https://..."]
  },
  "error": null
}
```

**GET /health**
- Response: `{ "status": "ok" }`

#### 지원 사이트
| 사이트 | 크롤러 | 상태 |
|--------|--------|------|
| Coupang | `crawlers/coupang.py` | 동작 중 |
| AliExpress | `crawlers/aliexpress.py` | 동작 중 |

---

## Supabase DB 스키마

```sql
-- 유저 (Supabase Auth 기본 제공)
-- auth.users 테이블 자동 생성

-- 유저별 등록 상품
CREATE TABLE products (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES auth.users(id) ON DELETE CASCADE,
    url TEXT NOT NULL,
    source TEXT NOT NULL,          -- 'coupang' | 'aliexpress'
    title TEXT,
    main_image TEXT,
    affiliate_id TEXT,             -- 제휴 API용 상품 ID
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);

-- SKU별 현재 가격
CREATE TABLE product_skus (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    product_id UUID REFERENCES products(id) ON DELETE CASCADE,
    sku_name TEXT NOT NULL,
    current_price INTEGER,         -- 원 단위 정수
    original_price INTEGER,
    image TEXT,
    updated_at TIMESTAMPTZ DEFAULT now()
);

-- 가격 이력
CREATE TABLE price_history (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    sku_id UUID REFERENCES product_skus(id) ON DELETE CASCADE,
    price INTEGER NOT NULL,
    recorded_at TIMESTAMPTZ DEFAULT now()
);

-- 인덱스
CREATE INDEX idx_products_user ON products(user_id);
CREATE INDEX idx_skus_product ON product_skus(product_id);
CREATE INDEX idx_history_sku ON price_history(sku_id, recorded_at DESC);
```

---

## 배치 프로세스 흐름

메인 서버에서 주기적으로 실행 (예: 6시간마다):

```
1. products 테이블에서 갱신 대상 조회
   │
2. Affiliate API로 가격 조회 시도
   │
   ├─ 성공 → 가격 업데이트
   │
   └─ 실패 (API 미지원 상품)
      │
3.    Crawler Server에 POST /crawl 요청
      │
      ├─ 성공 → 가격 업데이트
      │
      └─ 실패 → 에러 로그, 다음 배치에서 재시도
   │
4. 가격 변동 감지
   │
   ├─ product_skus.current_price 업데이트
   │
   └─ price_history에 새 레코드 삽입
   │
5. 가격 하락 시 유저에게 알림 (push notification)
```

---

## 가격 변동 추적 로직

```python
# 메인 서버 pseudo-code
def update_price(sku_id: str, new_price: int):
    old_price = get_current_price(sku_id)

    if old_price != new_price:
        # 현재 가격 업데이트
        update_sku_price(sku_id, new_price)

        # 이력 저장
        insert_price_history(sku_id, new_price)

        # 가격 하락 시 알림
        if new_price < old_price:
            drop_pct = (old_price - new_price) / old_price * 100
            notify_user(sku_id, old_price, new_price, drop_pct)
```

---

## 디렉토리 구조 (크롤링 서버)

```
gugu-crawler-server/
├── app.py              # FastAPI 앱 (POST /crawl, GET /health)
├── crawlers/
│   ├── __init__.py
│   ├── base.py         # 크롤러 베이스 클래스
│   ├── coupang.py      # 쿠팡 크롤러
│   └── aliexpress.py   # 알리익스프레스 크롤러
├── models/
│   ├── __init__.py
│   └── product.py      # Product, SkuPrice 모델
├── utils/              # 유틸리티
├── docs/               # 문서
└── requirements.txt
```
