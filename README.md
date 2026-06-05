# OMR Test Bot

O'qituvchilar uchun Telegram bot: guruh ochish, o'quvchi qo'shish, test yaratish,
javoblar varaqasi (titul) PDF generatsiya va OMR (computer vision) orqali skan o'qish.

## Texnologiyalar

- **Python 3.11+**, FastAPI, aiogram 3.x
- **DB**: PostgreSQL 16 + SQLAlchemy 2.0 async + Alembic
- **Queue**: Celery + Redis
- **CV/OMR**: OpenCV, NumPy, PyMuPDF, pyzbar, Pillow
- **PDF**: WeasyPrint + Jinja2 + qrcode
- **Deploy**: Docker + docker-compose

---

## Tezkor ishga tushirish

### 1. Muhit sozlash

Faylni nusxalang va o'zgartiring:
* **Windows (PowerShell)**: `Copy-Item .env.example .env`
* **Linux/macOS/GitBash**: `cp .env.example .env`

`.env` faylini ochib, quyidagilarni to'ldiring:
* **`BOT_TOKEN`** — [@BotFather](https://t.me/BotFather) dan olingan Telegram bot tokeni.
* **`BOT_USERNAME`** — Botingizning username-i (masalan, `omr_test_bot` shaklida).
* **`POSTGRES_USER` / `POSTGRES_PASSWORD` / `POSTGRES_DB`** — Ma'lumotlar bazasi hisob ma'lumotlari.

### 2. Konteynerlarni ishga tushirish

Loyiha barcha xizmatlarni (Postgres, Redis, API, Bot, Celery Worker, Loki, Grafana) Docker yordamida ko'taradi:

```bash
# 1. Tasvirlarni qurish (build)
docker compose build

# 2. Konteynerlarni orqa fonda ishga tushirish
docker compose up -d
```

> [!NOTE]
> Agar tizimingizda Docker Compose v1 bo'lsa, `docker compose` o'rniga `docker-compose` yozishingiz kerak.

### 3. Ma'lumotlar bazasi migratsiyasi

Sxema va jadvallarni PostgreSQL da yaratish uchun migratsiyani ishga tushiring:

```bash
docker compose exec api alembic upgrade head
```

### 4. Loglarni real vaqtda kuzatish (Loki & Grafana)

Loyiha real vaqtda loglarni yig'ish tizimiga ega. Agar botda biror muammo yoki xatolik yuz bersa, uni quyidagi interfeyslardan kuzatishingiz mumkin:

* **Grafana (Vizualizatsiya)**: [http://localhost:3000](http://localhost:3000)
  * **Login / Parol**: `admin` / `admin`
  * **Kuzatish**: Chap menyudan **Explore** bo'limiga o'ting, data source sifatida **Loki** tanlang va kerakli filtrni kiriting (masalan, `{service="bot"}` yoki `{service="worker"}`).
* **Loki (Log Ingestor)**: [http://localhost:3100](http://localhost:3100)

### 5. Bot ishga tushganini tekshirish

Telegram'da botingizga kirib `/start` buyrug'ini yuboring. Asosiy menyu ("📁 Mening guruhlarim", "➕ Guruh yaratish", "📝 Testlar") chiqishi kerak.

---

## Ishlatish oqimi

```
Ustoz:
  1. /start → asosiy menyu
  2. ➕ Guruh yaratish → nom kiritish
  3. Guruh → ➕ O'quvchi qo'shish → F.I.Sh (har qatorga bitta)
  4. Guruh → 📝 Test berish → nom → 40/50/90 → 4/5 variant
     → kalit kiritish (masalan: ABCDABCD... yoki 1-A, 2-C, ...)
  5. "Titullarni generatsiya qilaymi?" → Ha → PDF'lar yubortiladi
  6. PDF'larni chop etib o'quvchilarga bering

O'quvchi:
  1. Doiralarni bo'yash
  2. Skan qilish / rasmga olish
  3. Botga yuborish
  4. Natija keladi: "✅ 34/40 (85%)"
```

---

## OMR kalibrlash (muhim!)

`LAYOUTS_MM` dagi koordinatalar boshlang'ich taxmin. Birinchi ishga tushirishda
vizual tekshirish shart:

```bash
# 1. Annotatsiyalangan kalibrlash rasmi yaratish
docker-compose exec api python scripts/calibrate.py --qcount 40

# Yoki mavjud PDF bilan:
docker-compose exec api python scripts/calibrate.py --qcount 40 --pdf /data/pdfs/titul_1_1.pdf
```

`calibration_40.png` faylini oching:
- 🟢 Yashil kvadratlar = anchor (fiducial marker) markazlari
- 🔵 Ko'k doiralar = OMR o'qish markazlari

Agar ko'k doiralar varaqning haqiqiy doiralariga mos kelmasa,
`app/omr/layout.py` dagi `LAYOUTS_MM` ni sozlang:

```python
LAYOUTS_MM = {
  40: {
    "blocks": [
      {
        "x0": 35,   # ← o'zgartiring (blok chap chetidan mm)
        "y0": 100,  # ← o'zgartiring (blok yuqorisidan mm)
        "dx": 9,    # ← variant ustunlar oralig'i (mm)
        "dy": 8.5,  # ← savol qatorlar oralig'i (mm)
        "d": 6,     # ← doira diametri (mm)
        ...
      }
    ]
  }
}
```

Keyin `calibrate.py` ni qayta ishlatib tekshiring.

---

## Debug rejim

```bash
# .env da:
OMR_DEBUG=true

# Worker qayta ishga tushirish
docker compose restart worker
```

`OMR_DEBUG=true` da har skan uchun annotatsiyalangan rasm ham yuboriladi.
Annotatsiyada:
- 🔴 Qizil = tanlangan javob
- 🔵 Ko'k = tanlanmagan variantlar
- 🟡 Sariq chegara = ikkilanish (ambiguous)

---

## Test ishlatish

```bash
docker compose exec api pytest
```

---

## Muhim fayllar

| Fayl | Maqsad |
|---|---|
| `app/omr/layout.py` | Yagona haqiqat manbasi — doira koordinatalari |
| `app/pdf/render.py` | HTML → PDF renderer |
| `app/omr/pipeline.py` | To'liq OMR oqimi |
| `app/bot/handlers/` | Telegram bot oqimlari |
| `app/services/` | Biznes logika (bot + API ulashadi) |
| `scripts/calibrate.py` | Kalibrlash vositasi |

---

## Kengaytirish

- **Yangi savol soni**: `LAYOUTS_MM` ga yangi kalit qo'shing (masalan `30`),
  `titul_30.html` shablonini yarating, `chk_qcount` constraint'ni o'zgartiring.
- **Ko'p variantlar**: `vcount=5` allaqachon qo'llab-quvvatlanadi (A-E).
- **Web interfeys**: `app/api/` endpointlari tayyor — frontend ulash mumkin.

---

## Litsenziya

MIT © 2026
