# 크롤러 SKU 응답 → 내부 JSON 매핑

## 크롤러 원본 (aliexpress-test-result.md 기준)

```json
{
  "sku_name": "000000 / Asian size S",
  "price": "₩1,217",
  "original_price": "₩4,596",
  "image": "https://ae-pic-a1.aliexpress-media.com/kf/S888f2673816e4cf58bc9b672bc0588be4.jpg_220x220q75.jpg_.avif"
}
```

## Affiliate API 원본 (실측 기준)

```json
{
  "sku_id": 12000038514024193,
  "color": "000000",
  "size": "Asian size XXXL",
  "price_with_tax": "6246",
  "sale_price_with_tax": "5870",
  "currency": "KRW",
  "sku_image_link": "https://ae-pic-a1.aliexpress-media.com/kf/S888f2673816e4cf58bc9b672bc0588be4.jpg",
  "sku_properties": "[{\"색상\":\"000000\",\"크기\":\"Asian size XXXL\"}]"
}
```

## 우리 DB에 저장할 통합 포맷

### Affiliate API 경유 시

```json
{
  "external_sku_id": "12000038514024193",
  "sku_name": "000000 / Asian size XXXL",
  "color": "000000",
  "size": "Asian size XXXL",
  "price": "6246",
  "original_price": "5870",
  "currency": "KRW",
  "image_url": "https://ae-pic-a1.aliexpress-media.com/kf/S888f2673816e4cf58bc9b672bc0588be4.jpg",
  "sku_properties": "[{\"색상\":\"000000\",\"크기\":\"Asian size XXXL\"}]"
}
```

### 크롤러 경유 시

```json
{
  "external_sku_id": "000000 / Asian size S",
  "sku_name": "000000 / Asian size S",
  "color": "000000",
  "size": "Asian size S",
  "price": "1217",
  "original_price": "4596",
  "currency": "KRW",
  "image_url": "https://ae-pic-a1.aliexpress-media.com/kf/S888f2673816e4cf58bc9b672bc0588be4.jpg_220x220q75.jpg_.avif",
  "sku_properties": ""
}
```

## 매핑 규칙

| DB 컬럼 | Affiliate API | 크롤러 |
|---|---|---|
| `external_sku_id` | `str(sku_id)` → `"12000038514024193"` | `sku_name` → `"000000 / Asian size S"` |
| `sku_name` | `color + " / " + size` | `sku_name` 그대로 |
| `color` | `color` 필드 | `sku_name.split(" / ")[0]` |
| `size` | `size` 필드 | `sku_name.split(" / ")[1]` |
| `price` | `price_with_tax` (숫자) | `price`에서 통화기호/콤마 제거 (`"₩1,217"` → `"1217"`) |
| `original_price` | `sale_price_with_tax` (숫자) | `original_price`에서 통화기호/콤마 제거 (`"₩4,596"` → `"4596"`) |
| `currency` | `currency` 필드 | 통화기호에서 추출 (`₩` → `"KRW"`) |
| `image_url` | `sku_image_link` | `image` |
| `sku_properties` | JSON 원본 | `""` (빈 값) |

## 크롤러 파싱 시 주의사항

1. **가격 정제**: `"₩1,217"` → 통화기호 제거 → 콤마 제거 → `"1217"`
2. **통화 매핑**: `₩` → `KRW`, `$` → `USD`, `¥` → `CNY` 등
3. **color/size 분리**: `" / "` 구분자 기준 split, 구분자 없으면 전체를 color로
4. **external_sku_id**: sku_id가 없으므로 `sku_name` 값을 그대로 사용 (unique 제약 충족)
