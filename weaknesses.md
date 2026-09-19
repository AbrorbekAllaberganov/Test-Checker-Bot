# Loyiha zaifliklari (security / logika / bug)

Tahlil sanasi: 2026-09-15. Kod bazasi to'liq ko'rib chiqildi (API, bot, worker, OMR, modellar, migratsiyalar, infra, hali commit qilinmagan admin/SaaS qatlami). Jiddiylik bo'yicha tartiblangan.

Oldingi (iyun) ro'yxatdan tuzatilganlar: bot skanida `titul_id=None` (002 migratsiya), `omr_task` da qcount/vcount QR orqali aniqlash, web API ga initData auth qo'shilgan. Qolganlari va yangi topilganlar quyida.

---

> ✅ belgisi — tuzatilgan (qavsda task raqami va sana). Matn tarix uchun
> saqlanadi; bajarilish rejasi `tasks.md` da.
>
> **2026-09-19 holati: 37/37 band yopildi.** Qolgan yagona ish — bot
> tokenini BotFather orqali revoke qilish (buni faqat odam qila oladi).
> Qisqacha xulosa fayl oxiridagi "Holat" bo'limida.

## 🔴 KRITIK

1. ✅ *(qisman — T-01, 2026-09-16: fayldan olindi, CI skani qo'shildi; REVOKE hali qilinmagan)* **Haqiqiy bot tokeni git tarixida va u hozir ham ishlatilmoqda.** `.env.example:8` dagi token `591d758` (first commit) dan beri repoda. `.env` dagi joriy `BOT_TOKEN` aynan shu token. Repo ko'rgan har kim botni to'liq boshqaradi. Darhol BotFather orqali revoke qiling; faylni o'zgartirish yetarli emas.

2. ✅ *(T-07, 2026-09-16)* **Web dashboard'da tenant izolyatsiyasi yo'q (IDOR).** `app/api/routes/web_api.py` barcha endpointlar `get_webapp_user` bilan himoyalangan, lekin `user` hech qayerda ishlatilmaydi. Istalgan ro'yxatdan o'tgan ustoz: barcha guruhlar (`:83`), boshqa ustozning o'quvchilari (`:109`), **javob kalitlari** (`:228`), natijalar (`:237`, `:289`) ni ko'radi va **istalgan attempt bahosini o'zgartiradi** (`:350`). `dashboard-stats` (`:47`) butun tizim statistikasini beradi.

3. ✅ *(T-08, 2026-09-16)* **Bot callback'larida egalik tekshiruvi yo'q (IDOR).** Callback data soxtalashtirilsa boshqa ustozning ma'lumotlariga kirish/o'zgartirish mumkin: `groups.py:62-67` (`group:`), `students.py:18-23,45-49` (ro'yxat, qo'shish), `tests.py:71,100,292,314,337,363` (test yaratish, titullarni PDF/ZIP yuklab olish), `results.py:125,144,166,193,247,289,347,366,385` (natijalar, Excel eksport). `gen_tituls:all` (`tests.py:249`) FSM'dagi tekshirilmagan `test_id` bilan boshqa ustoz testiga titul generatsiya qilib PDF oladi. Faqat `del_group` va `menu_*` to'g'ri.

4. ✅ *(T-10, 2026-09-16)* **Statik fayllar autentifikatsiyasiz va taxmin qilinadigan nomlar bilan.** `app/api/main.py:49-51` — `/static/pdfs`, `/static/debug`, `/static/uploads`. PDF nomi `titul_{titul.id}_{student.id}.pdf` (`tasks.py:138-141`) — ID'lar ketma-ket, demak barcha o'quvchilar titullarini (F.I.Sh + QR) enumeratsiya qilib yuklab olish mumkin. QR'ga ega bo'lgan kishi o'quvchi nomidan soxta skan yuboradi. `/static/uploads` da o'quvchilar skanlari, `/static/debug` da annotatsiyalar.

5. ✅ *(T-02, 2026-09-16)* **Maxfiy kalitlar default qiymatda ishlashi mumkin.** `config.py:44` `internal_api_key="change-me"`, `:46` `secret_key="change-me-use-a-random-32-char-secret"`. Startup'da tekshiruv yo'q: `.env` da `SECRET_KEY` bo'lmasa admin JWT (`security.py:65`) ommaviy kalit bilan imzolanadi — istalgan kishi SUPERADMIN tokeni yasaydi.

6. ✅ *(T-03, 2026-09-16)* **Docker portlari hali ham internetga ochiq.** `docker-compose.yml`: Postgres `5433` (`:29`), **parolsiz Redis** `6380` (`:41`), API `8000`, Loki `3100` (`:78`), Grafana `3001` `admin/admin` (`:88-92`) — hammasi `0.0.0.0`. Port raqamini o'zgartirish himoya emas. Redis orqali Celery navbatiga istalgan task yuboriladi, FSM state'lar o'qiladi.

7. ✅ *(T-04, 2026-09-16)* **`.dockerignore` yo'q, `.env` va `.git` image ichiga kiradi.** `Dockerfile:34` `COPY . .`; root user; dev-deps; `compose:59` prod'da `--reload`.

8. ✅ *(T-05, 2026-09-16)* **Deploy tartibi noto'g'ri — 003 migratsiya uchun downtime kafolatlangan.** `deploy.yml:48-51` avval konteynerlar yangi kod bilan ko'tariladi, keyin `alembic upgrade`. Yangi `User` modeli `admin_role`, `is_blocked` ustunlarini SELECT qiladi → migratsiya tugaguncha bot ham, API ham yiqiladi. CI'da test yo'q, rollback yo'q.

---

## 🟠 YUQORI

9. ✅ *(T-26, 2026-09-19)* **API `/attempts/scan` hali ham buzuq.** `attempts.py:62` `titul_id=1` placeholder (FK xato yoki noto'g'ri bog'lanish); `:57` fayl nomi `id(content)` — qayta ishlatiladigan qiymat, ustma-ust yozish; `:47` butun fayl o'qilib keyin hajm tekshiriladi (RAM DoS). `schemas/attempts.py:12` `titul_id: int` — pending/error attempt uchun `GET /attempts/{id}` 500 qaytaradi.

10. ✅ *(T-09 + T-17, 2026-09-16: ro'yxatsiz skan rad, titul egaligi worker'da, guruh/o'quvchi limiti botda, /start'da obuna, middleware ro'yxat+blok)* **SaaS kvota/blok mantiqi hech qayerda chaqirilmaydi.** `services/subscriptions.py` dagi `consume_scan`, `check_group_limit`, `check_student_limit`, `ensure_subscription` — bot va API'da ishlatilmaydi. `scan.py:95-174` da ro'yxat/blok/kvota tekshiruvi yo'q: istalgan Telegram foydalanuvchisi (o'quvchi ham) skan yuboradi. `admin/users.py:457` "bot middleware `is_blocked` tekshiradi" deydi — bunday middleware yo'q, blok botda ishlamaydi. Yangi ustozlarga obuna yaratilmaydi (faqat 003 seed'dagilar). `last_seen_at` hech qachon yangilanmaydi.

11. ✅ *(T-11, 2026-09-16)* **FSM handlerlari matn bo'lmagan xabarda yiqiladi.** `groups.py:95`, `students.py:70`, `tests.py:114,164` — `message.text.strip()` `F.text` filtrsiz. Holatda turib rasm/stiker yuborilsa `AttributeError`, javob yo'q, state tiqilib qoladi. Ustoz kalit kiritish holatida turib skan yuborsa ham shu.

12. ✅ *(T-21 varianti A, 2026-09-19: 5 variant tanlovdan olib tashlandi, `VALID_OPTIONS="ABCD"`; eski testlarga ogohlantirish. Layout'ga E qo'shish — alohida sprint)* **5 variantli test aslida ishlamaydi.** `layout.py:30,37,44` `options` faqat `ABCD`; `options[:vcount]` 5 uchun ham 4 ta beradi. Bot 5 variantni tanlashga (`inline.py:100`) va kalitda `E` kiritishga ruxsat beradi, lekin PDF'da E doirasi chizilmaydi va OMR o'qimaydi → `E` javoblar doim xato.

13. ✅ *(T-20, 2026-09-19)* **Varaq teskari (180°) tushsa natija indamay noto'g'ri.** `anchors.py:24-45` `order_points` rasm burchaklarini oladi, fizik yo'nalishni (QR joylashuvi) tekshirmaydi → grid oynadek buriladi, hamma javob "xato". Anchor filtri (`:19-21`) piksel maydoniga bog'liq: telefon 12MP suratda doiralar/QR finder kvadratlari anchor deb olinishi yoki haqiqiy anchor `MAX_AREA` dan oshishi mumkin; 4 nuqta to'rtburchak hosil qilishi tekshirilmaydi.

14. ✅ *(T-18 + T-23, 2026-09-19)* **Worker resurs DoS.** `tasks.py:218` va `:260` faylni ikki marta to'liq yuklaydi (`read_qr_from_file` PDF ning **barcha** sahifalarini rasterizatsiya qiladi, faqat 0-sahifa kerak). 20 MB ichida yuzlab sahifali PDF yoki decompression-bomb PNG → worker OOM. `celery_app.py` da `task_time_limit`/`soft_time_limit` yo'q: `acks_late=True` bilan osilgan task 1 soatdan keyin qayta yetkaziladi (dublikat). `tasks.py:31-40` har taskda yangi engine.

15. ✅ *(T-19, 2026-09-19)* **`omr_task` xato oqimi.** `tasks.py:370-388` istalgan xatoda foydalanuvchiga xabar yuborib **keyin** retry — 3 marta bir xil xabar; doimiy xatolar ham retry. `bubble_data`/`confidence` (003 ustunlari) attempt'ga yozilmaydi (`:330-341`) → admin OMR inspektori bo'sh bo'ladi.

16. ✅ *(T-12, 2026-09-16)* **Telegram HTML injection.** `parse_mode=HTML` bilan escape qilinmagan foydalanuvchi matni: `grading.py:99-100`, `groups.py:74,114`, `tests.py:124,229,304`, `results.py:137,181,282`, `start.py:63`, `tasks.py:170`, `admin/users.py:502` (blok sababi). `<b>` yoki `<` kiritilsa Telegram "can't parse entities" → handler yiqiladi.

17. ✅ *(T-13, 2026-09-16)* **Excel/CSV formula injection.** `excel.py:136-146` va `history.py:168-177` — `=`, `+`, `-`, `@` bilan boshlangan F.I.Sh/test nomi hujayraga to'g'ridan-to'g'ri yoziladi. `results.py:358,377,396` fayl nomlari sanitizatsiyasiz (`/`, `"`).

18. ✅ *(`ends_at` — 2026-09-16; T-39 anchor_day — 2026-09-19)* **Obuna muddati hech qachon tugamaydi.** `subscriptions.py:130-144` `get_active_subscription` `ends_at` ni tekshirmaydi, statusni `expired` ga o'tkazadigan joy yo'q → to'lov muddati o'tgan tarif cheksiz ishlaydi. `:86-91` `_next_period_end` kunni 28 ga qisqartiradi — davr har oy oldinga siljiydi. `:384` tarif almashganda `scans_used` ko'chib o'tadi.

19. ✅ *(T-30, 2026-09-19)* **Admin OTP oqimi.** `admin/auth.py:160-168` — `retry_after` faqat admin ID uchun qaytadi → admin telegram_id'larini enumeratsiya qilish mumkin. IP bo'yicha limit yo'q → har adminga 60 s da bitta OTP spam. `audit.py:33-40` `X-Forwarded-For` ko'r-ko'rona ishoniladi (soxtalash). `admin/auth.py:302-335` refresh "rotatsiya" deyilgan, lekin eski refresh token bekor qilinmaydi, logout yo'q — 14 kun ichida sizib chiqqan token to'liq ishlaydi.

20. ✅ *(T-28, 2026-09-19)* **initData replay.** `routes/auth.py:36` `_INIT_DATA_MAX_AGE = 0` — bir marta tutib olingan `initData` abadiy amal qiladi (`/api/web/*` ham, `/api/admin/auth/telegram` ham).

21. ✅ *(CORS — 2026-09-16; T-29 `/docs` — 2026-09-19)* **CORS `*` + `allow_credentials=True`** (`main.py:40-46`), `/docs` va `/redoc` prod'da ochiq (`:36-37`).

22. ✅ *(T-24, 2026-09-19)* **Telegram flood limitlari.** `tests.py:276-279` har o'quvchi uchun alohida `pdf_task` + `send_document` (150 o'quvchi = 150 xabar), `tasks.py:84-91` `RetryAfter` faqat log qilinadi → ba'zi PDF'lar indamay yetib bormaydi. `tests.py:377-388` ZIP xotirada, 50 MB dan oshsa yuborilmaydi.

---

## 🟡 O'RTA

23. ✅ *(T-18, 2026-09-19: ogohlantirish qo'shildi; har sahifani alohida urinish qilish — alohida feature)* **Ko'p sahifali PDF'da faqat 1-sahifa tekshiriladi** (`tasks.py:278`), ogohlantirish yo'q.

24. ✅ *(T-27, 2026-09-19)* **Qo'lda tuzatish nomuvofiq.** `attempts.py:101-106` `score` ni yangilab `percent`/`detail` ni qayta hisoblamaydi. `web_api.py:373-382` `corrected_answers` variant soniga tekshirilmaydi, `manual_override`/`reviewed_by_id`/`reviewed_at` to'ldirilmaydi.

25. ✅ *(T-14, 2026-09-16; o'quvchini botga ulash oqimi — alohida reja)* **O'lik/tugallanmagan UI.** `inline.py:152` `results:{test_id}` tugmasi uchun handler yo'q (aylanib turadi). `results.py:51` reply-keyboard matni hech qachon kelmaydi (`reply.py` ishlatilmaydi). `students.py:137` `link_telegram` chaqirilmaydi — dashboard doim "Ulanmagan".

26. ✅ *(T-15, 2026-09-16)* **Foydalanuvchi ma'lumoti eskiradi.** `services/groups.py:16-31` ikkinchi `/start` da ism/username yangilanmaydi; callback orqali yaratilgan userlar `full_name=NULL`.

27. ✅ *(T-16, 2026-09-16)* **`parse_key` takror raqamlarni indamay ustidan yozadi** (`services/tests.py:55-65`): "1-A 1-B 2-C" 2 savolli test uchun qabul qilinadi.

28. ✅ *(T-32, 2026-09-19)* **Timezone.** `web_api.py:56` naive `datetime.now()`; Celery `Asia/Tashkent` (`celery_app.py:24`), ilova UTC. "Bugungi skanlar" O'zbekiston kuni bo'yicha noto'g'ri.

29. ✅ *(T-33, 2026-09-19)* **`get_db` har GET'da ham commit qiladi** (`db.py:57-66`).

30. ✅ *(T-25, 2026-09-19: UUID nom, HEIC rad, `uploads_dir` + kunlik `cleanup_temp_files`; albom kollektori ongli murosa)* **Skan qabul qilish nozikliklari.** `scan.py:26-28` albom kollektori xotirada (restart'da yo'qoladi, 3 s timeout); `:41` fayl nomi `file_id` — bir xil rasm qayta yuborilsa worker o'qiyotgan fayl ustidan yoziladi; `image/heic` qabul qilinadi, lekin OpenCV o'qiy olmaydi; vaqtinchalik fayllar hech qachon tozalanmaydi (review ularga bog'liq).

31. ✅ *(T-34, 2026-09-19)* **Loki handler** (`logging.py:14,54-57`): chegarasiz navbat, Loki yotsa har yozuv 3 s ushlanadi → xotira o'sadi.

32. ✅ *(T-23, 2026-09-19)* **Celery natijalari ishlatilmaydi, lekin 24 soat Redis'da saqlanadi** (`celery_app.py:15,30`) — `ignore_result=True` kerak.

33. ✅ *(T-22, 2026-09-19)* **`fill_ratio` har doira uchun to'liq kadr niqob yaratadi** (`bubbles.py:39-41`), 360 doira × 1449×2134 → sekin.

34. ✅ *(T-35, 2026-09-19)* **Testlar haqiqiy bazaga yozadi/o'chiradi** (`test_web_api.py:24-31,150-167`), izolyatsiya yo'q; prod `.env` bilan ishga tushirilsa ma'lumot buziladi.

35. ✅ *(router — 2026-09-16; T-31 `ilike` escape — 2026-09-19)* **Admin API hali yarim.** `api/admin/__init__.py:8` `router` moduli, `admin/users.py:256` `admin_export` — endi yaratilmoqda; `main.py` ga ulanmagan. `users.py:118` `ilike` da `%`/`_` escape qilinmagan.

36. ✅ *(T-36, 2026-09-19)* **Docs/kod nomuvofiqligi.** `.env.example` "hammasini to'ldiring" deydi-yu, haqiqiy qiymatlar bilan keladi; `docs/06_API.md` yo'llari koddan farq qiladi; o'quvchi oqimlari hujjatda bor, kodda yo'q.

---

## 🟢 PAST

37. ✅ *(T-37 + T-38, 2026-09-19)* Dockerfile: multi-stage yo'q, `HEALTHCHECK` yo'q; `scratch/*.png|jpg` (real skan) git'da; `attempts` da `user_id`/`chat_id` yo'q (kim yuborgani noma'lum); backup strategiyasi yo'q; metrik/alert yo'q; `verify_internal_key` doimiy vaqtli solishtirmaydi.

    Bajarildi: Dockerfile multi-stage (gcc runtime'da qolmaydi) + `HEALTHCHECK`;
    `scratch/*.png|jpg` git'dan olindi va `.gitignore` ga qo'shildi;
    `attempts.submitted_by_id` (004 migratsiya) + egalik zanjirida ishlatiladi;
    `docs/08` §8.4 backup, §8.5 monitoring; `/health` DB va Redis'ni tekshiradi
    va nosozda 503 beradi; Grafana `level=ERROR` alert qoidasi.
    `verify_internal_key` allaqachon `hmac.compare_digest` ishlatadi (T-02).

---

## Holat (2026-09-19)

**37 banddan 37 tasi yopildi.** Reja va bajarilish tafsilotlari `tasks.md` da.

Qolgan ish **faqat odam qila oladigan** bitta narsa:

- **№1 — bot tokenini BotFather orqali revoke qilish.** Token eski
  commitlarda qolgan va hozir ham ishlatilmoqda. Kod tomonidan qilinadigan
  hamma narsa bajarilgan (fayldan olindi, CI skani, `.gitignore`).
  Git tarixini qayta yozish (`filter-repo`) — foydalanuvchi qarori:
  barcha klonlar sinadi. Batafsil: `QOLGAN_ISHLAR.md`.

Ongli ravishda **to'liq yopilmagan**, lekin xavfsiz holatga keltirilgan
murosalar (ular zaiflik emas, qabul qilingan cheklov):

| Band | Murosa |
|---|---|
| №12 | 5 variantli test **o'chirildi** (A varianti). Layout'ga `E` qo'shish kalibrlash talab qiladi — alohida sprint. |
| №23 | Ko'p sahifali PDF'dan faqat 1-sahifa tekshiriladi, lekin endi **ogohlantirish** beriladi. Har sahifani alohida urinish qilish — alohida feature. |
| №25 | O'quvchini botga ulash oqimi yozilmagan (`docs/05` "Rejalashtirilgan" bo'limi). |
| №30 | Albom kollektori jarayon xotirasida — bot restart bo'lsa yig'ilayotgan albom yo'qoladi. Yetim fayllar kunlik tozalanadi. |
| №37 | Grafana alert **kontakt nuqtasi** repoga qo'yilmagan (sir bo'lgani uchun) — UI'da sozlanadi. |

### Tekshirish

```bash
# Testlar (izolyatsiyalangan baza bilan)
docker compose exec -T postgres psql -U omruser -d postgres -c "CREATE DATABASE omrdb_test"
docker compose run --rm --no-deps \
  -e TEST_DATABASE_URL="postgresql+asyncpg://omruser:PAROL@postgres:5432/omrdb_test" \
  api pytest app/tests -q

# Frontend
cd admin-ui && npm run typecheck && npm run build

# Migratsiya
docker compose run --rm --no-deps api alembic upgrade head   # 004 gacha

# Sirlar git'da yo'qligi (1 kutiladi)
grep -rnE '[0-9]{8,}:[A-Za-z0-9_-]{35}' --exclude-dir=.git . ; echo $?
```
