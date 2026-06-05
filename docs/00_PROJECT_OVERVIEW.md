# OMR Test Bot — Loyiha Umumiy Ko'rinishi

## Maqsad

Telegram bot (+ ixtiyoriy web). Ustozlar guruh ochadi, o'quvchi qo'shadi, test
yaratadi. Har o'quvchiga A4 titul (javoblar varaqasi) PDF generatsiya qilinadi.
O'quvchi qog'ozni qo'lda to'ldiradi (dumaloqlarni bo'yaydi), skanlaydi/rasmga
oladi va botga yuboradi. Bot **OMR** (Optical Mark Recognition) orqali javoblarni
o'qiydi, ustoz kiritgan kalit bilan solishtiradi va natija hamda natijalar
tarixini chiqaradi.

## Asosiy qarorlar (FIXED)

| Qaror | Tanlov |
|---|---|
| OMR usuli | **Anchor-markerli fixed-grid** (4 burchakka qora kvadrat) |
| To'g'ri javob kaliti | **Ustoz qo'lda kiritadi** (bot orqali) |
| Auth | **Faqat Telegram** (telegram_id = identity) |
| Test turlari | 40, 50, 90 savol |
| Variant soni | A, B, C, D (4 ta) — konfiguratsiyalanadi |
| ID o'tkazish | Har titulda **QR code** (test_id + student_id) |

## Texnologiyalar

- **Backend / API**: FastAPI (async)
- **Bot**: aiogram 3.x
- **DB**: PostgreSQL + SQLAlchemy 2.0 (async) + Alembic
- **Queue**: Celery + Redis (OMR va PDF og'ir ishlari fonda)
- **CV / OMR**: OpenCV, NumPy, PyMuPDF (fitz), pyzbar (QR), Pillow
- **PDF generatsiya**: HTML shablon -> WeasyPrint (yoki Playwright) -> PDF
- **QR generatsiya**: qrcode + Pillow
- **Konteyner**: Docker + docker-compose

## Yuqori darajadagi oqim (flow)

```
Ustoz:  /start -> guruh yaratadi -> o'quvchi qo'shadi -> test yaratadi
        -> savollar soni + variant + KALIT kiritadi
        -> "Titullarni generatsiya qil" -> bot har o'quvchiga PDF beradi (bitta ZIP yoki alohida)

O'quvchi (qog'ozda): dumaloqlarni bo'yaydi -> skanlaydi -> botga rasm/PDF yuboradi

Bot:    rasm -> Celery task -> QR o'qish -> anchor topish -> perspektiva to'g'rilash
        -> grid bo'yicha har dumaloqni o'lchash -> javoblar -> kalit bilan solishtirish
        -> natija saqlash -> ustoz va o'quvchiga natija + tarix
```

## Hujjatlar ro'yxati

- `01_ARCHITECTURE.md` — komponentlar, papka tuzilishi, deploy
- `02_DATABASE.md` — to'liq DB sxema (DDL + tushuntirish)
- `03_OMR_PIPELINE.md` — eng muhim: dumaloq o'qish algoritmi
- `04_PDF_TEMPLATES.md` — titul shablonlar spetsifikatsiyasi (anchor + QR + grid)
- `05_BOT_FLOWS.md` — bot menyu/state mashinasi
- `06_API.md` — FastAPI endpointlar
- `07_ANTIGRAVITY_PROMPT.md` — Antigravity'ga beriladigan asosiy build prompt

## Loyiha qurish tartibi (Antigravity uchun)

1. Skelet: docker-compose (postgres, redis, api, bot, worker), .env, settings
2. DB modellari + Alembic migration (02 ga qarab)
3. HTML titul shablonlari (3 ta) + PDF renderer (04 ga qarab)
4. QR + anchor generatsiya, titul PDF yaratish servisi
5. Bot flow'lari (05 ga qarab)
6. OMR pipeline + Celery task (03 ga qarab) — eng katta qism
7. Natija/tarix saqlash va xabar yuborish
8. Integratsiya testlari (namuna skanlar bilan)
