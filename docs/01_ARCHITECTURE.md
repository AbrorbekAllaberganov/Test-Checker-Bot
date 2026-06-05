# 01 — Arxitektura

## Komponentlar

```
                ┌────────────────┐
   Telegram ───>│   Bot (aiogram)│
                └───────┬────────┘
                        │ HTTP (internal)
                        v
                ┌────────────────┐      ┌──────────────┐
                │  FastAPI (API) │<────>│  PostgreSQL  │
                └───────┬────────┘      └──────────────┘
                        │ enqueue
                        v
                ┌────────────────┐      ┌──────────────┐
                │  Celery worker │<────>│    Redis     │
                │  (OMR + PDF)   │      └──────────────┘
                └────────────────┘
```

- **Bot** faqat Telegram bilan gaplashadi, biznes-logikani API'ga yuboradi.
  (Bot to'g'ridan-to'g'ri DB'ga ham yozishi mumkin — kichik loyihada soddaroq.
  Tavsiya: bot va api **bitta kodbaza**, servis qatlamini ulashadi.)
- **API** REST endpointlar (web kelajakda ulanishi uchun) + servis qatlami.
- **Celery worker** og'ir vazifalar: skan rasmni OMR qilish, ko'p sahifali PDF
  generatsiya. Telegram'da fayl yuklash bloklashmasligi uchun shart.
- **Redis** — Celery broker + natija backend + bot FSM storage.
- **PostgreSQL** — barcha doimiy ma'lumot.

## Papka tuzilishi

```
omr-test-bot/
├─ docker-compose.yml
├─ .env.example
├─ pyproject.toml            # yoki requirements.txt
├─ alembic.ini
├─ app/
│  ├─ core/
│  │  ├─ config.py           # Pydantic Settings (env)
│  │  ├─ db.py               # async engine, session
│  │  └─ logging.py
│  ├─ models/                # SQLAlchemy modellar
│  │  ├─ user.py  group.py  student.py  test.py  attempt.py
│  ├─ schemas/               # Pydantic schemalar
│  ├─ services/              # biznes-logika (bot ham, api ham ishlatadi)
│  │  ├─ groups.py  tests.py  titul.py  grading.py  history.py
│  ├─ omr/                   # COMPUTER VISION
│  │  ├─ pipeline.py         # asosiy: image -> answers
│  │  ├─ anchors.py          # anchor topish + perspektiva
│  │  ├─ qr.py               # QR o'qish
│  │  ├─ bubbles.py          # dumaloqlarni o'lchash
│  │  ├─ layout.py           # 40/50/90 grid koordinatalari
│  │  └─ debug.py            # debug rasm chizish
│  ├─ pdf/
│  │  ├─ render.py           # html -> pdf (weasyprint)
│  │  ├─ qrgen.py
│  │  └─ templates/
│  │     ├─ base.html
│  │     ├─ titul_40.html
│  │     ├─ titul_50.html
│  │     └─ titul_90.html
│  ├─ api/
│  │  ├─ main.py             # FastAPI app
│  │  └─ routes/
│  ├─ bot/
│  │  ├─ main.py             # aiogram dispatcher
│  │  ├─ handlers/
│  │  ├─ keyboards/
│  │  └─ states.py           # FSM
│  ├─ worker/
│  │  ├─ celery_app.py
│  │  └─ tasks.py            # omr_task, pdf_task
│  └─ tests/
└─ docs/
```

## Konteynerlar (docker-compose servislari)

- `postgres` (volume bilan)
- `redis`
- `api` (uvicorn app.api.main:app)
- `bot` (python -m app.bot.main)
- `worker` (celery -A app.worker.celery_app worker)
- (ixtiyoriy) `flower` — Celery monitoring

## Konfiguratsiya (.env)

```
BOT_TOKEN=
DATABASE_URL=postgresql+asyncpg://user:pass@postgres:5432/omr
SYNC_DATABASE_URL=postgresql+psycopg://user:pass@postgres:5432/omr  # alembic/celery
REDIS_URL=redis://redis:6379/0
ADMIN_TELEGRAM_IDS=12345678        # super-admin
MAX_IMAGE_MB=20
OMR_DEBUG=false
```

## Xavfsizlik / cheklovlar

- Telegram_id = identity. Birinchi /start qilgan -> oddiy foydalanuvchi.
- Faqat guruh egasi (ustoz) o'sha guruh testlarini boshqaradi.
- O'quvchi QR'siz skan yuborsa -> "QR topilmadi" xatosi.
- Yuborilgan rasm hajmi cheklanadi (MAX_IMAGE_MB).
- OMR ishonch darajasi past bo'lsa (noaniq dumaloq) -> flag bilan ustozga
  "qo'lda tekshiring" deb belgilanadi.
