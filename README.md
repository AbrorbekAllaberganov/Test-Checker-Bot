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

> [!TIP]
> Kundalik buyruqlar (ishga tushirish, to'xtatish, rebuild, loglar,
> muammolarni hal qilish) alohida faylda: **[ISHGA_TUSHIRISH.md](ISHGA_TUSHIRISH.md)**.

## Tezkor ishga tushirish

### 1. Muhit sozlash

Faylni nusxalang va o'zgartiring:
* **Windows (PowerShell)**: `Copy-Item .env.example .env`
* **Linux/macOS/GitBash**: `cp .env.example .env`

`.env` faylini ochib, barcha `CHANGE_ME_...` qiymatlarni almashtiring:
* **`BOT_TOKEN`** — [@BotFather](https://t.me/BotFather) dan olingan Telegram bot tokeni.
* **`BOT_USERNAME`** — Botingizning username-i (masalan, `omr_test_bot` shaklida).
* **`POSTGRES_PASSWORD`** — baza paroli. `DATABASE_URL` va `SYNC_DATABASE_URL` ichidagi parol bilan **bir xil** bo'lishi shart.
* **`REDIS_PASSWORD`** — Redis paroli. `REDIS_URL` ichidagi parol bilan **bir xil** bo'lishi shart (`redis://:PAROL@redis:6379/0`).
* **`SECRET_KEY`**, **`INTERNAL_API_KEY`** — tasodifiy kalitlar (quyidagi buyruq bilan).
* **`GRAFANA_ADMIN_PASSWORD`** — Grafana admin paroli.

```bash
python -c "import secrets; print(secrets.token_hex(32))"
```

> [!WARNING]
> `.env.example` ga hech qachon haqiqiy token yoki parol yozmang — u git'da turadi va uni repo ko'rgan har kim o'qiydi. Sirlar faqat `.env` da (u `.gitignore` da).

`REDIS_PASSWORD`, `POSTGRES_PASSWORD` va `GRAFANA_ADMIN_PASSWORD` bo'sh bo'lsa `docker compose` ataylab ishga tushmaydi va qaysi o'zgaruvchi yetishmayotganini aytadi.

### 2. Konteynerlarni ishga tushirish

Loyiha barcha xizmatlarni (Postgres, Redis, API, Bot, Celery Worker, Loki, Grafana) Docker yordamida ko'taradi:

```bash
# 1. Tasvirlarni qurish (build)
docker compose build

# 2. Baza va Redis
docker compose up -d postgres redis

# 3. Migratsiya — ilova konteynerlaridan OLDIN (pastdagi izohga qarang)
docker compose run --rm api alembic upgrade head

# 4. Qolgan konteynerlarni orqa fonda ishga tushirish
docker compose up -d
```

> [!IMPORTANT]
> Migratsiya **har doim** `up -d` dan oldin bajariladi. Yangi kod yangi ustunlarni o'qiydi — teskari tartibda bot ham, API ham migratsiya tugaguncha yiqilib turadi.

> [!NOTE]
> Agar tizimingizda Docker Compose v1 bo'lsa, `docker compose` o'rniga `docker-compose` yozishingiz kerak.

### 3. Portlar va xavfsizlik

Barcha portlar **faqat `127.0.0.1`** ga bog'langan — Postgres, Redis, Grafana va Loki internetdan ko'rinmaydi. Serverda API oldida HTTPS beruvchi reverse proxy (nginx/caddy) turishi kutiladi.

Uzoqdagi serverda panelni ochish uchun SSH tunnel:

```bash
ssh -L 8000:127.0.0.1:8000 -L 3001:127.0.0.1:3001 user@server
```

Reverse proxy yo'q bo'lsa va API portini ochish kerak bo'lsa, `.env` da `API_BIND_HOST=0.0.0.0` (tavsiya etilmaydi).

Konteynerlar ichida ilova `root` emas, `appuser` (uid 10001) nomidan ishlaydi.

### 4. Loglarni real vaqtda kuzatish (Loki & Grafana)

Loyiha real vaqtda loglarni yig'ish tizimiga ega. Agar botda biror muammo yoki xatolik yuz bersa, uni quyidagi interfeyslardan kuzatishingiz mumkin:

* **Grafana (Vizualizatsiya)**: [http://127.0.0.1:3001](http://127.0.0.1:3001)
  * **Login / Parol**: `admin` / `.env` dagi `GRAFANA_ADMIN_PASSWORD`
  * **Kuzatish**: Chap menyudan **Explore** bo'limiga o'ting, data source sifatida **Loki** tanlang va kerakli filtrni kiriting (masalan, `{service="bot"}` yoki `{service="worker"}`).
* **Loki (Log Ingestor)**: [http://127.0.0.1:3100](http://127.0.0.1:3100)

Ikkalasi ham faqat lokal interfeysda — uzoq serverda SSH tunnel orqali oching.

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
