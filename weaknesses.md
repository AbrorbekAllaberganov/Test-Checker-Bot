# Loyiha kamchiliklari (weaknesses)

Tahlil sanasi: 2026-06-11. Quyidagi ro'yxat kod bazasini to'liq ko'rib chiqish asosida tuzilgan va jiddiylik darajasi bo'yicha tartiblangan.

---

## 🔴 KRITIK — darhol tuzatish kerak

### 1. `.env.example` ichida haqiqiy bot tokeni git'ga commit qilingan
`.env.example:8` da haqiqiy ko'rinishdagi Telegram bot tokeni bor (`8642853215:AAG...`) va bu fayl git tarixida saqlanadi. Repo kimga ko'rinsa, bot to'liq egallab olinishi mumkin.
**Yechim:** Tokenni darhol BotFather orqali bekor qiling (revoke), `.env.example` ga placeholder qo'ying. Token git tarixida qolgani uchun faqat faylni o'zgartirish yetarli emas.

### 2. Web dashboard API'da umuman autentifikatsiya yo'q
Boshqa barcha routerlar `verify_internal_key` bilan himoyalangan, lekin `app/api/routes/web_api.py` routerida hech qanday himoya yo'q. Istalgan odam:
- barcha guruhlar, o'quvchilar (F.I.Sh, telegram_id), test kalitlari (`answer_key`!) va natijalarni ko'ra oladi;
- `POST /api/web/attempts/{id}/review` orqali **istalgan o'quvchining bahosini o'zgartira oladi**.

### 3. OMR pipeline har doim 40-savollik, 4-variantlik grid bilan o'qiydi
`app/worker/tasks.py:215` da `run()` chaqirilganda `qcount`/`vcount` berilmaydi, `app/omr/pipeline.py:184` esa default 40 savol / 4 variant qabul qiladi. QR avval o'qilsa ham, titul→test dan haqiqiy savol soni olinib pipeline'ga qaytarilmaydi. Natijada **50 va 90 savollik titullar noto'g'ri tekshiriladi** (41+ savollar o'qilmaydi, grid koordinatalari ham boshqa layoutga to'g'ri kelmaydi), 5 variantli testlarda E varianti o'qilmaydi.

### 4. `titul_id=1` placeholder — yangi bazada scan oqimi butunlay ishlamaydi
`app/bot/handlers/scan.py:55` da pending attempt `titul_id=1` bilan yaratiladi. ID=1 titul mavjud bo'lmasa FK xatosi tushadi va birorta skan ishlamaydi; mavjud bo'lsa, xato bilan tugagan attemptlar boshqa o'quvchining tituliga bog'lanib qoladi (statistika buziladi).

### 5. Maxfiy fayllar autentifikatsiyasiz statik tarzda ochiq
`app/api/main.py:49-51` — `/static/pdfs`, `/static/debug`, `/static/uploads` mountlari himoyasiz. O'quvchilarning skan qilingan varaqlari, F.I.Sh yozilgan PDF titullar va debug rasmlar URL'ni bilgan (yoki taxmin qilgan) har kimga ochiq. Fayl nomlari Telegram `file_id` (taxmin qilish qiyin), lekin web API ulardagi yo'llarni ochiq qaytaradi (2-band bilan birga to'liq ma'lumot sizib chiqadi).

### 6. Docker'da Postgres, Redis, Grafana, Loki portlari tashqariga ochiq
`docker-compose.yml`:
- `5432:5432` va `6379:6379` — VPS'da bu Postgres (parol `omrpass` default) va **parolsiz Redis**ni butun internetga ochadi. Redis orqali Celery navbatiga zararli tasklar ham yuborilishi mumkin;
- Grafana `admin/admin` paroli hardcode qilingan (`GF_SECURITY_ADMIN_PASSWORD=admin`), `3000` port ochiq;
- Loki `3100` autentifikatsiyasiz ochiq — istalgan kishi log o'qiy oladi/yoza oladi;
- Flower (`5555`) ham autentifikatsiyasiz.
**Yechim:** portlarni faqat `127.0.0.1:` ga bind qilish yoki umuman publish qilmaslik, Redis'ga parol qo'yish.

### 7. `.dockerignore` yo'q — `.env` va o'quvchi skanlari Docker image ichiga kiradi
`Dockerfile:34` `COPY . .` butun papkani ko'chiradi: `.env` (haqiqiy tokenlar bilan), `scratch/omr_uploads/` dagi haqiqiy o'quvchi PDF skanlari, docs, git fayllari — hammasi image qatlamlariga yoziladi. Image biror registry'ga push qilinsa, sirlar tarqaydi.

---

## 🟠 YUQORI — xavfsizlik va to'g'rilik muammolari

### 8. Bot'da egalik (ownership) tekshiruvi yo'q joylar — IDOR
`app/bot/handlers/groups.py:62-78` — `group:{id}` callback'ida `get_group()` ishlatiladi (`get_group_for_owner` emas). Foydalanuvchi callback data'ni soxtalashtirsa, **boshqa ustozning guruhini ochishi** (va menyu orqali o'quvchilarini, testlarini boshqarishi) mumkin. API'dagi `GET /groups/{id}`, `POST /{id}/students` ham owner tekshirmaydi.

### 9. Istalgan Telegram foydalanuvchisi skan yuborib natija olishi mumkin
`scan.py` da hech qanday ro'yxatdan o'tish/rol tekshiruvi yo'q. O'quvchining o'zi ham varaqni suratga olib botga yuborsa, javob kalitiga nisbatan natijani (qaysi savollar to'g'ri/xato) ko'ra oladi — bu test sirini buzadi. `admin_telegram_ids` sozlamasi mavjud, lekin **kodda hech qayerda ishlatilmaydi**.

### 10. CORS hamma uchun ochiq
`app/api/main.py:40-46` — `allow_origins=["*"]` + `allow_credentials=True` birga. Bu kombinatsiya spec bo'yicha noto'g'ri va xavfli; autentifikatsiya qo'shilganda ham CSRF-ga yo'l ochadi.

### 11. CI/CD'da test/lint bosqichi yo'q, migratsiya tartibi noto'g'ri
`.github/workflows/deploy.yml`:
- push → to'g'ridan-to'g'ri deploy, testlar umuman ishga tushirilmaydi;
- konteynerlar **avval** yangi kod bilan ko'tariladi, migratsiya **keyin** ishlaydi (51-qator) — sxema mos kelmagan oraliqda xatolar bo'ladi;
- rollback mexanizmi yo'q, `git pull` server'dagi lokal o'zgarishlarda yiqiladi;
- "downtimesiz" deb yozilgan, lekin `docker-compose up --build` aslida downtime beradi.

### 12. Production'da `--reload` rejimi
`docker-compose.yml:59` — API `uvicorn ... --reload` bilan ishlaydi. Bu dev rejimi: sekin, xotira sarfi katta, fayl-watcher prod'da keraksiz. Dev/prod uchun bitta compose fayl ishlatilgan, override fayl yo'q.

### 13. Celery task'da har safar yangi DB engine yaratiladi
`app/worker/tasks.py:31-40` — `_get_sync_session()` har chaqiruvda `create_engine()` qiladi va engine hech qachon dispose qilinmaydi → connection pool'lar to'planib, Postgres ulanishlari tugashi mumkin. Engine module darajasida bitta bo'lishi kerak.

### 14. Xatoda retry + foydalanuvchiga takror xabar
`omr_task` (tasks.py:323-341) istalgan istisnoda attempt'ni `error` qilib, foydalanuvchiga xabar yuborib, **keyin retry qiladi** — foydalanuvchi 2-3 marta bir xil "Xatolik yuz berdi" xabarini oladi, retry muvaffaqiyatli bo'lsa ham status chalkashadi. Doimiy xatolar (masalan, noto'g'ri UUID) retry qilinmasligi kerak.

### 15. Ko'p sahifali PDF'da faqat birinchi sahifa tekshiriladi
`tasks.py:231` — `results[0]` olinadi, qolgan sahifalar **indamay tashlab yuboriladi**. Ustoz 30 varaqni bitta PDF qilib yuborsa, faqat 1 tasi tekshiriladi va hech qanday ogohlantirish yo'q.

---

## 🟡 O'RTA — funksional va arxitektura kamchiliklari

### 16. Album "jamlama natija" va'da qilingan, lekin yo'q
`scan.py` docstring'ida "jamlama natija" deyilgan, amalda har rasm alohida xabar yuboradi. 30 ta varaq yuborilsa, 60+ xabar keladi. Albom kollektor xotirada (`_album_collector` dict) — bot restart bo'lsa yo'qoladi, bir nechta bot instance'da ishlamaydi.

### 17. Vaqtinchalik fayllar hech qachon tozalanmaydi
Yuklab olingan skanlar (`/tmp/omr_uploads`), generatsiya qilingan PDF'lar va debug rasmlar uchun hech qanday cleanup/retention siyosati yo'q — disk asta-sekin to'ladi. Shu bilan birga `attempt.source_file` shu papkaga ishora qiladi, ya'ni fayllarni tozalash review funksiyasini sindiradi — bu bog'liqlik hal qilinmagan.

### 18. Timezone bilan ishlash noto'g'ri
`web_api.py:53` — `datetime.now()` (naive, server lokal vaqti) `TIMESTAMPTZ` ustun bilan solishtiriladi → "bugungi skanlar" statistikasi UTC/lokal farqida noto'g'ri chiqadi. Loyihada umuman timezone strategiyasi yo'q (foydalanuvchilar O'zbekistonda, server UTC bo'lishi mumkin).

### 19. Pipeline'dagi `needs_review` mantiqiy nomuvofiq
`pipeline.py:197-200` — kommentda "ambiguous yoki blank" deyilgan, kodda faqat `ambiguous` tekshiriladi. Blank flag'lar pipeline darajasida e'tiborsiz (grade() ichida qoplanadi, lekin ikki joyda ikki xil mantiq — chalkash).

### 20. `warp_w/warp_h` qiymatlari config va .env.example'da har xil
`config.py:62-63` default `1449x2134`, `.env.example:51-52` esa `1654x2339`. Kalibratsiya qaysi o'lchamda qilingan bo'lsa, boshqasida bubble koordinatalari suriladi. Bunday "sinxron bo'lishi shart" qiymatlar bitta manbada bo'lishi kerak.

### 21. Race condition: parallel skanlar va album timeout'i
`ALBUM_TIMEOUT = 3.0` — sekin internetda albom rasmlari 3 soniyadan kechiksa, albom bo'linib ketadi. `_album_collector` global dict — bir foydalanuvchi spam qilsa xotira o'sadi, eski yozuvlar tozalanmaydi (faqat muvaffaqiyatli yo'lda `pop` qilinadi).

### 22. Rate limiting / flood himoyasi yo'q
Bot ham, API ham cheklovsiz. Bitta foydalanuvchi yuzlab rasm yuborib Celery navbatini va diskni to'ldira oladi. Photo handler'da hajm tekshiruvi ham yo'q (document'da bor, photo'da yo'q).

### 23. Migratsiya bilan modellarning sinxronligi kafolatlanmagan
Bitta `001_initial.py` migratsiya bor; model o'zgarishlari uchun autogenerate jarayoni yo'lga qo'yilmagan. `attempts.titul_id` `NOT NULL` — placeholder muammosining (4-band) ildizi shu sxemada: skan kelganda titul hali noma'lum bo'lishi tabiiy holat, ustun nullable bo'lishi kerak edi.

### 24. Test qamrovi juda past
`app/tests/` — faqat grade, key parse, layout va web_api uchun minimal testlar. Eng murakkab va xatoga moyil qismlar: `scan.py` oqimi, `omr_task`, anchors/warp, bot FSM handlerlari — umuman testlanmagan. CI'da testlar ishlatilmagani uchun mavjudlari ham himoya bermaydi.

### 25. `get_db` dependency har so'rovda avtomatik commit qiladi
`app/core/db.py:57-66` — GET so'rovlarda ham commit, xatosiz tugagan har qanday handler o'zgarishni saqlaydi. Read-only endpointlar uchun ortiqcha; tranzaksiya chegaralarini service qatlamida nazorat qilish to'g'riroq.

---

## 🟢 PAST — sifat va texnik qarz

### 26. Dockerfile optimallashtirilmagan
- Multi-stage build yo'q: `gcc`, `python3-dev` va dev-dependencylar (`pip install -e ".[dev]"` — pytest, factory-boy) production image'da qoladi;
- Konteyner **root** foydalanuvchisida ishlaydi;
- `HEALTHCHECK` yo'q.

### 27. `scratch/` papkasi va binar fayllar repoda
Debug skriptlar, kalibratsiya rasmlari, real o'quvchi skanlari (`scratch/omr_uploads/*.pdf` — lokal, lekin `scratch/*.png/jpg` git'da) repo og'irligini oshiradi va chalkashlik tug'diradi. `docs/sample_titul_*.pdf` `.gitignore`dagi `*.pdf` qoidasiga zid ravishda tracked.

### 28. `attempts` jadvalida `chat_id` saqlanmaydi
Natija kimga yuborilgani DB'da yo'q — keyinchalik qayta yuborish/audit qilib bo'lmaydi. Shuningdek attempt'da `user_id` yo'q — skanlarni kim yuborganini bilish imkonsiz.

### 29. Loki handler'dagi cheksiz navbat va yo'qotilgan loglar
`app/core/logging.py` — `queue.Queue` chegarasiz (Loki uzoq yotsa xotira o'sadi), xatoda log yozuvi yo'qoladi, graceful shutdown yo'q (daemon thread navbatdagi loglarni tashlab ketadi).

### 30. HTML-injection xavfi xabarlarda
Bot xabarlari `ParseMode.HTML` bilan yuboriladi va `student.full_name`, `test.title`, `group.name` kabi foydalanuvchi kiritgan matnlar escape qilinmasdan qo'shiladi (`grading.py:format_result_message`, handlerlar). `<b>` kabi teglar kiritilsa xabar buziladi yoki Telegram xato qaytaradi.

### 31. README/docs bilan kod o'rtasida nomuvofiqliklar
Docs'da tasvirlangan oqimlar (masalan, album jamlama, qcount aniqlash) kodda to'liq amalga oshmagan. `CLAUDE.md` yo'q. `.env.example`dagi izoh "BARCHA maydonlarni to'ldiring" deydi, lekin haqiqiy qiymatlar bilan kelgan.

### 32. Monitoring/alerting amaliy emas
Loki+Grafana bor-u, lekin metrikalar (navbat uzunligi, OMR muvaffaqiyat foizi, xato darajasi) yig'ilmaydi, alert yo'q. Faqat deploy haqida Telegram xabari bor.

### 33. Backup strategiyasi yo'q
Postgres ma'lumotlari (barcha guruh/test/natijalar) uchun hech qanday zaxira mexanizmi yo'q — `pg_data` volume yo'qolsa, hamma narsa yo'qoladi.

---

## Tavsiya etiladigan birinchi qadamlar (tartib bilan)

1. Bot tokenini revoke qilish va `.env.example`ni tozalash (№1).
2. `web_api` routeriga autentifikatsiya qo'shish yoki Telegram WebApp `initData` tekshiruvini joriy qilish (№2, №5).
3. `omr_task`da titul→test orqali `qcount`/`vcount`ni aniqlab pipeline'ni qayta chaqirish (№3).
4. `attempts.titul_id`ni nullable qilish va placeholder'ni olib tashlash (№4).
5. Docker portlarini yopish, Redis'ga parol, `.dockerignore` qo'shish (№6, №7).
6. CI'ga test bosqichi qo'shish (№11, №24).
