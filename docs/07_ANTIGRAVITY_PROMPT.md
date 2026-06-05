# 07 — Antigravity Build Prompt

> Bu faylni Antigravity'ga to'liq nusxalab bering. U `docs/` papkadagi boshqa
> MD fayllarni ham o'qiy oladi — ularga murojaat qiladi.

---

## PROMPT (Antigravity'ga)

Quyidagi spetsifikatsiya asosida to'liq ishlaydigan loyiha qur. Loyiha — o'qituvchilar
uchun Telegram bot: guruh ochish, o'quvchi qo'shish, test yaratish, har o'quvchiga
A4 javoblar varaqasi (titul) PDF generatsiya qilish, o'quvchi qo'lda to'ldirib
skanlagan varaqni OMR (computer vision) orqali o'qish, baholash va natijalar
tarixini saqlash.

Batafsil spetsifikatsiya `docs/` papkasida:
- `docs/00_PROJECT_OVERVIEW.md` — umumiy
- `docs/01_ARCHITECTURE.md` — arxitektura, papka tuzilishi
- `docs/02_DATABASE.md` — PostgreSQL sxema (shu DDL ga aniq amal qil)
- `docs/03_OMR_PIPELINE.md` — dumaloq o'qish algoritmi (eng muhim, aynan shunday qil)
- `docs/04_PDF_TEMPLATES.md` — titul HTML/PDF spetsifikatsiyasi
- `docs/05_BOT_FLOWS.md` — bot menyu va FSM
- `docs/06_API.md` — endpointlar va servislar

### Texnologiyalar (qat'iy)
- Python 3.11+
- FastAPI (async) + uvicorn
- aiogram 3.x (Telegram bot)
- SQLAlchemy 2.0 async + asyncpg + Alembic
- Celery + Redis
- OpenCV (opencv-python-headless), NumPy, PyMuPDF (fitz), pyzbar, Pillow
- WeasyPrint (HTML->PDF), Jinja2, qrcode
- Docker + docker-compose

### Talablar
1. `docs/01` dagi aynan papka tuzilishini yarat.
2. `docs/02` dagi DDL ga to'liq mos SQLAlchemy modellari + birinchi Alembic migration.
   `pgcrypto` extension migration ichida yoqilsin.
3. `app/omr/layout.py` da `LAYOUTS_MM` ni yarat va `build_bubble_positions()`
   hamda `omr_grid_px()` funksiyalarini implement qil. Bu **yagona haqiqat manbasi**:
   PDF shu koordinatadan doira chizadi, OMR shu koordinatadan o'qiydi.
3 ta HTML shablon (`titul_40/50/90.html`) `docs/04` ga mos — 4 anchor + QR +
   meta maydonlar + grid doiralar (jinja loop bilan `build_bubble_positions` dan).
4. `app/pdf/render.py`, `qrgen.py` — titul PDF generatsiya.
5. `app/omr/` pipeline'ni `docs/03` ga aynan mos implement qil:
   `qr.py`, `anchors.py` (order_points + perspektiva), `bubbles.py` (fill_ratio),
   `pipeline.py` (to'liq oqim), `debug.py` (annotatsiya). Konstantalar
   (FILL_MIN, MARGIN, DPI, WARP_W/H) `core/config.py` da, env'dan o'qiladigan.
6. `app/bot/` — `docs/05` dagi barcha oqimlar: guruh/o'quvchi/test yaratish,
   kalit parse (ikkala format), titul generatsiya (alohida + ZIP), skan qabul
   (photo, document image, PDF, media group, ko'p sahifali PDF), natija + tarix.
   FSM uchun Redis storage.
7. `app/worker/tasks.py` — `pdf_task`, `omr_task`. Bot uzoq ishni Celery'ga beradi,
   darhol "⏳" yozadi, task tugagach natijani yuboradi.
8. `app/api/` — `docs/06` endpointlari + `app/services/` servis qatlami
   (bot ham, api ham shu servislardan foydalanadi — logika takrorlanmasin).
9. `docker-compose.yml`: postgres, redis, api, bot, worker (+ ixtiyoriy flower).
   `.env.example`, `README.md` (ishga tushirish: migrate, up).
10. `app/tests/` — kamida: kalit parse testlari, layout koordinata testlari,
    grade() testi, va `fixtures/` ga namuna skan + kutilgan natija bilan OMR
    regression testi uchun skelet.

### Sifat talablari
- Type hints, docstring, modulli, takrorlanmaydigan kod.
- Xatolarni foydalanuvchiga tushunarli xabar bilan qaytar (`docs/05` jadvali).
- `OMR_DEBUG=true` da har attempt uchun annotatsiyalangan debug rasm saqla.
- needs_review (past ishonchli OMR) ni DB'da belgila va ustozga ko'rsat.
- Hech qaerda real API kalit/parol hardcode qilma; hammasi `.env` orqali.

### Birinchi navbatda (MVP ketma-ketligi)
Avval skelet + docker-compose + DB + migration ishlasin. Keyin 40-talik titul
PDF to'liq ishlasin (anchor+QR+grid). Keyin OMR pipeline 40-talik uchun ishlasin
va debug rasm bilan tasdiqlansin. Keyin 50 va 90 ga kengaytir. Bot oqimlarini
shu tartibda ula.

### Muhim ogohlantirish (OMR kalibrlash)
`LAYOUTS_MM` dagi koordinatalar boshlang'ich taxmin. Loyiha qurilgach, namuna
titul PDF generatsiya qilib, uni "to'ldirilgan" deb simulyatsiya qilib (yoki
chop etib-skanlab), `OMR_DEBUG` bilan doiralar to'g'ri tushganini tekshirish va
`LAYOUTS_MM` ni sozlash kerakligini README'da yoz. Bu qadamni avtomatlashtirish
uchun `scripts/calibrate.py` — generatsiya qilingan PDF ni rasterga aylantirib,
grid markazlarini ustiga chizib ko'rsatadigan yordamchi skript ham yarat.

---

## Antigravity'ga keyingi buyruqlar (ketma-ket)
1. "Skelet + docker-compose + DB modellari + migrationni qur va ishlat."
2. "layout.py va 40-talik titul HTML/PDF ni qur, namuna PDF generatsiya qil."
3. "scripts/calibrate.py bilan grid to'g'riligini ko'rsat."
4. "OMR pipeline (40-talik) ni qur, debug rasm bilan tekshir."
5. "Bot oqimlarini ula (guruh/o'quvchi/test/titul)."
6. "Skan qabul + omr_task + natija/tarixni ula."
7. "50 va 90 talikni qo'sh."
