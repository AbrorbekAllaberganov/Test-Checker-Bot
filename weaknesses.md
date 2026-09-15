# Loyiha zaifliklari (security / logika / bug)

Tahlil sanasi: 2026-09-15. Kod bazasi to'liq ko'rib chiqildi (API, bot, worker, OMR, modellar, migratsiyalar, infra, hali commit qilinmagan admin/SaaS qatlami). Jiddiylik bo'yicha tartiblangan.

Oldingi (iyun) ro'yxatdan tuzatilganlar: bot skanida `titul_id=None` (002 migratsiya), `omr_task` da qcount/vcount QR orqali aniqlash, web API ga initData auth qo'shilgan. Qolganlari va yangi topilganlar quyida.

---

## 🔴 KRITIK

1. **Haqiqiy bot tokeni git tarixida va u hozir ham ishlatilmoqda.** `.env.example:8` dagi token `591d758` (first commit) dan beri repoda. `.env` dagi joriy `BOT_TOKEN` aynan shu token. Repo ko'rgan har kim botni to'liq boshqaradi. Darhol BotFather orqali revoke qiling; faylni o'zgartirish yetarli emas.

2. **Web dashboard'da tenant izolyatsiyasi yo'q (IDOR).** `app/api/routes/web_api.py` barcha endpointlar `get_webapp_user` bilan himoyalangan, lekin `user` hech qayerda ishlatilmaydi. Istalgan ro'yxatdan o'tgan ustoz: barcha guruhlar (`:83`), boshqa ustozning o'quvchilari (`:109`), **javob kalitlari** (`:228`), natijalar (`:237`, `:289`) ni ko'radi va **istalgan attempt bahosini o'zgartiradi** (`:350`). `dashboard-stats` (`:47`) butun tizim statistikasini beradi.

3. **Bot callback'larida egalik tekshiruvi yo'q (IDOR).** Callback data soxtalashtirilsa boshqa ustozning ma'lumotlariga kirish/o'zgartirish mumkin: `groups.py:62-67` (`group:`), `students.py:18-23,45-49` (ro'yxat, qo'shish), `tests.py:71,100,292,314,337,363` (test yaratish, titullarni PDF/ZIP yuklab olish), `results.py:125,144,166,193,247,289,347,366,385` (natijalar, Excel eksport). `gen_tituls:all` (`tests.py:249`) FSM'dagi tekshirilmagan `test_id` bilan boshqa ustoz testiga titul generatsiya qilib PDF oladi. Faqat `del_group` va `menu_*` to'g'ri.

4. **Statik fayllar autentifikatsiyasiz va taxmin qilinadigan nomlar bilan.** `app/api/main.py:49-51` — `/static/pdfs`, `/static/debug`, `/static/uploads`. PDF nomi `titul_{titul.id}_{student.id}.pdf` (`tasks.py:138-141`) — ID'lar ketma-ket, demak barcha o'quvchilar titullarini (F.I.Sh + QR) enumeratsiya qilib yuklab olish mumkin. QR'ga ega bo'lgan kishi o'quvchi nomidan soxta skan yuboradi. `/static/uploads` da o'quvchilar skanlari, `/static/debug` da annotatsiyalar.

5. **Maxfiy kalitlar default qiymatda ishlashi mumkin.** `config.py:44` `internal_api_key="change-me"`, `:46` `secret_key="change-me-use-a-random-32-char-secret"`. Startup'da tekshiruv yo'q: `.env` da `SECRET_KEY` bo'lmasa admin JWT (`security.py:65`) ommaviy kalit bilan imzolanadi — istalgan kishi SUPERADMIN tokeni yasaydi.

6. **Docker portlari hali ham internetga ochiq.** `docker-compose.yml`: Postgres `5433` (`:29`), **parolsiz Redis** `6380` (`:41`), API `8000`, Loki `3100` (`:78`), Grafana `3001` `admin/admin` (`:88-92`) — hammasi `0.0.0.0`. Port raqamini o'zgartirish himoya emas. Redis orqali Celery navbatiga istalgan task yuboriladi, FSM state'lar o'qiladi.

7. **`.dockerignore` yo'q, `.env` va `.git` image ichiga kiradi.** `Dockerfile:34` `COPY . .`; root user; dev-deps; `compose:59` prod'da `--reload`.

8. **Deploy tartibi noto'g'ri — 003 migratsiya uchun downtime kafolatlangan.** `deploy.yml:48-51` avval konteynerlar yangi kod bilan ko'tariladi, keyin `alembic upgrade`. Yangi `User` modeli `admin_role`, `is_blocked` ustunlarini SELECT qiladi → migratsiya tugaguncha bot ham, API ham yiqiladi. CI'da test yo'q, rollback yo'q.

---

## 🟠 YUQORI

9. **API `/attempts/scan` hali ham buzuq.** `attempts.py:62` `titul_id=1` placeholder (FK xato yoki noto'g'ri bog'lanish); `:57` fayl nomi `id(content)` — qayta ishlatiladigan qiymat, ustma-ust yozish; `:47` butun fayl o'qilib keyin hajm tekshiriladi (RAM DoS). `schemas/attempts.py:12` `titul_id: int` — pending/error attempt uchun `GET /attempts/{id}` 500 qaytaradi.

10. **SaaS kvota/blok mantiqi hech qayerda chaqirilmaydi.** `services/subscriptions.py` dagi `consume_scan`, `check_group_limit`, `check_student_limit`, `ensure_subscription` — bot va API'da ishlatilmaydi. `scan.py:95-174` da ro'yxat/blok/kvota tekshiruvi yo'q: istalgan Telegram foydalanuvchisi (o'quvchi ham) skan yuboradi. `admin/users.py:457` "bot middleware `is_blocked` tekshiradi" deydi — bunday middleware yo'q, blok botda ishlamaydi. Yangi ustozlarga obuna yaratilmaydi (faqat 003 seed'dagilar). `last_seen_at` hech qachon yangilanmaydi.

11. **FSM handlerlari matn bo'lmagan xabarda yiqiladi.** `groups.py:95`, `students.py:70`, `tests.py:114,164` — `message.text.strip()` `F.text` filtrsiz. Holatda turib rasm/stiker yuborilsa `AttributeError`, javob yo'q, state tiqilib qoladi. Ustoz kalit kiritish holatida turib skan yuborsa ham shu.

12. **5 variantli test aslida ishlamaydi.** `layout.py:30,37,44` `options` faqat `ABCD`; `options[:vcount]` 5 uchun ham 4 ta beradi. Bot 5 variantni tanlashga (`inline.py:100`) va kalitda `E` kiritishga ruxsat beradi, lekin PDF'da E doirasi chizilmaydi va OMR o'qimaydi → `E` javoblar doim xato.

13. **Varaq teskari (180°) tushsa natija indamay noto'g'ri.** `anchors.py:24-45` `order_points` rasm burchaklarini oladi, fizik yo'nalishni (QR joylashuvi) tekshirmaydi → grid oynadek buriladi, hamma javob "xato". Anchor filtri (`:19-21`) piksel maydoniga bog'liq: telefon 12MP suratda doiralar/QR finder kvadratlari anchor deb olinishi yoki haqiqiy anchor `MAX_AREA` dan oshishi mumkin; 4 nuqta to'rtburchak hosil qilishi tekshirilmaydi.

14. **Worker resurs DoS.** `tasks.py:218` va `:260` faylni ikki marta to'liq yuklaydi (`read_qr_from_file` PDF ning **barcha** sahifalarini rasterizatsiya qiladi, faqat 0-sahifa kerak). 20 MB ichida yuzlab sahifali PDF yoki decompression-bomb PNG → worker OOM. `celery_app.py` da `task_time_limit`/`soft_time_limit` yo'q: `acks_late=True` bilan osilgan task 1 soatdan keyin qayta yetkaziladi (dublikat). `tasks.py:31-40` har taskda yangi engine.

15. **`omr_task` xato oqimi.** `tasks.py:370-388` istalgan xatoda foydalanuvchiga xabar yuborib **keyin** retry — 3 marta bir xil xabar; doimiy xatolar ham retry. `bubble_data`/`confidence` (003 ustunlari) attempt'ga yozilmaydi (`:330-341`) → admin OMR inspektori bo'sh bo'ladi.

16. **Telegram HTML injection.** `parse_mode=HTML` bilan escape qilinmagan foydalanuvchi matni: `grading.py:99-100`, `groups.py:74,114`, `tests.py:124,229,304`, `results.py:137,181,282`, `start.py:63`, `tasks.py:170`, `admin/users.py:502` (blok sababi). `<b>` yoki `<` kiritilsa Telegram "can't parse entities" → handler yiqiladi.

17. **Excel/CSV formula injection.** `excel.py:136-146` va `history.py:168-177` — `=`, `+`, `-`, `@` bilan boshlangan F.I.Sh/test nomi hujayraga to'g'ridan-to'g'ri yoziladi. `results.py:358,377,396` fayl nomlari sanitizatsiyasiz (`/`, `"`).

18. **Obuna muddati hech qachon tugamaydi.** `subscriptions.py:130-144` `get_active_subscription` `ends_at` ni tekshirmaydi, statusni `expired` ga o'tkazadigan joy yo'q → to'lov muddati o'tgan tarif cheksiz ishlaydi. `:86-91` `_next_period_end` kunni 28 ga qisqartiradi — davr har oy oldinga siljiydi. `:384` tarif almashganda `scans_used` ko'chib o'tadi.

19. **Admin OTP oqimi.** `admin/auth.py:160-168` — `retry_after` faqat admin ID uchun qaytadi → admin telegram_id'larini enumeratsiya qilish mumkin. IP bo'yicha limit yo'q → har adminga 60 s da bitta OTP spam. `audit.py:33-40` `X-Forwarded-For` ko'r-ko'rona ishoniladi (soxtalash). `admin/auth.py:302-335` refresh "rotatsiya" deyilgan, lekin eski refresh token bekor qilinmaydi, logout yo'q — 14 kun ichida sizib chiqqan token to'liq ishlaydi.

20. **initData replay.** `routes/auth.py:36` `_INIT_DATA_MAX_AGE = 0` — bir marta tutib olingan `initData` abadiy amal qiladi (`/api/web/*` ham, `/api/admin/auth/telegram` ham).

21. **CORS `*` + `allow_credentials=True`** (`main.py:40-46`), `/docs` va `/redoc` prod'da ochiq (`:36-37`).

22. **Telegram flood limitlari.** `tests.py:276-279` har o'quvchi uchun alohida `pdf_task` + `send_document` (150 o'quvchi = 150 xabar), `tasks.py:84-91` `RetryAfter` faqat log qilinadi → ba'zi PDF'lar indamay yetib bormaydi. `tests.py:377-388` ZIP xotirada, 50 MB dan oshsa yuborilmaydi.

---

## 🟡 O'RTA

23. **Ko'p sahifali PDF'da faqat 1-sahifa tekshiriladi** (`tasks.py:278`), ogohlantirish yo'q.

24. **Qo'lda tuzatish nomuvofiq.** `attempts.py:101-106` `score` ni yangilab `percent`/`detail` ni qayta hisoblamaydi. `web_api.py:373-382` `corrected_answers` variant soniga tekshirilmaydi, `manual_override`/`reviewed_by_id`/`reviewed_at` to'ldirilmaydi.

25. **O'lik/tugallanmagan UI.** `inline.py:152` `results:{test_id}` tugmasi uchun handler yo'q (aylanib turadi). `results.py:51` reply-keyboard matni hech qachon kelmaydi (`reply.py` ishlatilmaydi). `students.py:137` `link_telegram` chaqirilmaydi — dashboard doim "Ulanmagan".

26. **Foydalanuvchi ma'lumoti eskiradi.** `services/groups.py:16-31` ikkinchi `/start` da ism/username yangilanmaydi; callback orqali yaratilgan userlar `full_name=NULL`.

27. **`parse_key` takror raqamlarni indamay ustidan yozadi** (`services/tests.py:55-65`): "1-A 1-B 2-C" 2 savolli test uchun qabul qilinadi.

28. **Timezone.** `web_api.py:56` naive `datetime.now()`; Celery `Asia/Tashkent` (`celery_app.py:24`), ilova UTC. "Bugungi skanlar" O'zbekiston kuni bo'yicha noto'g'ri.

29. **`get_db` har GET'da ham commit qiladi** (`db.py:57-66`).

30. **Skan qabul qilish nozikliklari.** `scan.py:26-28` albom kollektori xotirada (restart'da yo'qoladi, 3 s timeout); `:41` fayl nomi `file_id` — bir xil rasm qayta yuborilsa worker o'qiyotgan fayl ustidan yoziladi; `image/heic` qabul qilinadi, lekin OpenCV o'qiy olmaydi; vaqtinchalik fayllar hech qachon tozalanmaydi (review ularga bog'liq).

31. **Loki handler** (`logging.py:14,54-57`): chegarasiz navbat, Loki yotsa har yozuv 3 s ushlanadi → xotira o'sadi.

32. **Celery natijalari ishlatilmaydi, lekin 24 soat Redis'da saqlanadi** (`celery_app.py:15,30`) — `ignore_result=True` kerak.

33. **`fill_ratio` har doira uchun to'liq kadr niqob yaratadi** (`bubbles.py:39-41`), 360 doira × 1449×2134 → sekin.

34. **Testlar haqiqiy bazaga yozadi/o'chiradi** (`test_web_api.py:24-31,150-167`), izolyatsiya yo'q; prod `.env` bilan ishga tushirilsa ma'lumot buziladi.

35. **Admin API hali yarim.** `api/admin/__init__.py:8` `router` moduli, `admin/users.py:256` `admin_export` — endi yaratilmoqda; `main.py` ga ulanmagan. `users.py:118` `ilike` da `%`/`_` escape qilinmagan.

36. **Docs/kod nomuvofiqligi.** `.env.example` "hammasini to'ldiring" deydi-yu, haqiqiy qiymatlar bilan keladi; `docs/06_API.md` yo'llari koddan farq qiladi; o'quvchi oqimlari hujjatda bor, kodda yo'q.

---

## 🟢 PAST

37. Dockerfile: multi-stage yo'q, `HEALTHCHECK` yo'q; `scratch/*.png|jpg` (real skan) git'da; `attempts` da `user_id`/`chat_id` yo'q (kim yuborgani noma'lum); backup strategiyasi yo'q; metrik/alert yo'q; `verify_internal_key` doimiy vaqtli solishtirmaydi.

---

## Birinchi qadamlar (tartib bilan)

1. Bot tokenini revoke qilish, `.env.example` ni tozalash, `SECRET_KEY`/`INTERNAL_API_KEY` default bo'lsa startup'da yiqilish (№1, №5).
2. `web_api.py` da har so'rovni `user.id` bo'yicha filtrlash; bot callback'larida `get_group_for_owner` orqali egalik tekshiruvi (№2, №3).
3. Statik mountlarni olib tashlab, fayllarni auth'li endpoint orqali berish; PDF nomiga UUID (№4).
4. Compose portlarini `127.0.0.1:` ga bog'lash, Redis parol, `.dockerignore`, `--reload` ni olib tashlash (№6, №7).
5. Deploy'da migratsiyani konteynerlardan **oldin** ishga tushirish, CI'ga pytest (№8).
6. Skan oqimiga ro'yxat/blok/kvota tekshiruvi va bot middleware (№10); FSM handlerlarga `F.text` (№11); 5 variantni layout'ga qo'shish yoki tanlovdan olib tashlash (№12).
