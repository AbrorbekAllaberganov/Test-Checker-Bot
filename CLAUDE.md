# CLAUDE.md

OMR Test Bot — o'qituvchilar uchun Telegram bot (guruh → o'quvchi → test →
titul PDF → OpenCV orqali skan o'qish) + React admin panel (SaaS: tarif,
kvota, moderatsiya).

Bu fayl har sessiyada kontekstga yuklanadi. Shu sababli bu yerda faqat
**qayta kashf qilish qimmatga tushadigan** narsalar bor. Kod tuzilishini
gapirmaydi — uni `Glob`/`Grep` bilan topish arzon.

---

## Buyruqlar

```bash
docker compose build              # HAMMA image (api+bot+worker) — quyidagi tuzoqqa qarang
docker compose up -d
docker compose run --rm --no-deps api alembic upgrade head
docker compose run --rm --no-deps api pytest app/tests -q   # DB testlari SKIP
docker compose logs -f api bot worker beat
```

Frontend (`admin-ui/`):

```bash
npm run typecheck && npm run build   # ikkalasi ham toza bo'lishi shart
npm run dev                          # :5173, /api va /static ni :8000 ga proksi qiladi
```

Baza (dev):

```bash
docker compose exec -T postgres psql -U omruser -d omrdb -c "SELECT ..."
```

**DB testlari alohida bazani talab qiladi** (aks holda `skip`):

```bash
docker compose exec -T postgres psql -U omruser -d postgres -c "CREATE DATABASE omrdb_test"
docker compose run --rm --no-deps \
  -e TEST_DATABASE_URL="postgresql+asyncpg://omruser:PAROL@postgres:5432/omrdb_test" \
  api pytest app/tests -q
```

URL ichida `test` so'zi bo'lishi SHART — pytest aks holda darhol to'xtaydi.

---

## Tuzoqlar (bularni bilmasangiz vaqt yo'qotasiz)

**1. `api`, `bot`, `worker` — AYRIM image'lar, bitta Dockerfile'dan.**
`docker compose build api` faqat api'ni yangilaydi; bot va worker eski
kodda qolib ketadi va nosozlik "sirli" ko'rinadi. Model yoki `app/services/`
o'zgarsa — `docker compose build` (servis nomisiz) qiling.
Compose'da source volume mount YO'Q → har o'zgarishda rebuild kerak.
`build` konteynerni QAYTA ISHGA TUSHIRMAYDI — keyin `docker compose up -d`
ham qiling, aks holda konteyner eski image'da qolib, o'zgarish "yetib
kelmagandek" ko'rinadi. Admin panel `dist` ham shu image ichida yig'iladi.

**2. Barcha `TIMESTAMPTZ` ustunlari tz-aware datetime talab qiladi.**
`datetime.now()` (naive) bilan solishtirish asyncpg'da
`DataError: can't subtract offset-naive and offset-aware` beradi.
Har doim `datetime.now(timezone.utc)`. Yangi model ustuni yozsangiz —
`mapped_column(TIMESTAMP(timezone=True), ...)`, turini tashlab ketmang
(SQLAlchemy naive `DateTime` deb o'ylab qoladi).
Teskari holat: **openpyxl tz-aware datetime'ni qabul qilmaydi** —
Excel eksportda `dt.replace(tzinfo=None)`.

**3. Bitta `AsyncSession` parallel ishlatilmaydi.**
`asyncio.gather(...)` ichiga bitta sessiyaga boradigan ikkita so'rov
qo'ymang — "concurrent operations" xatosi. DB chaqiruvlari ketma-ket.

**4. Async'da lazy-load yo'q.**
Relationship'ga tegadigan bo'lsangiz `selectinload` zanjirini OXIRIGACHA
yozing (`Attempt.titul → Titul.test → Test.group → Group.owner`), aks holda
`MissingGreenlet`.

**5. Admin roli TOKENDAN emas, BAZADAN o'qiladi** (`api/admin/deps.py`).
JWT ichidagi `role` faqat ma'lumot uchun. RBAC'ni token yasab test qilib
bo'lmaydi — `users.admin_role` ni bazada o'zgartiring.

**6. `SECRET_KEY` namunaviy bo'lsa admin panel ATAYLAB ishlamaydi.**
`core/security.py: assert_secret_is_safe()` token berishni ham, qabul
qilishni ham rad etadi (503). Bu bug emas. Bot va Mini App bunga bog'liq
emas — ular `bot_token` HMAC'idan foydalanadi.

**7. Compose endi majburiy sirlarni talab qiladi.**
`.env` da `POSTGRES_PASSWORD`, `REDIS_PASSWORD`, `GRAFANA_ADMIN_PASSWORD`
bo'lmasa `docker compose` umuman ishga tushmaydi (bu ataylab).
`REDIS_URL` ichidagi parol `REDIS_PASSWORD` bilan bir xil bo'lishi shart —
compose `env_file` ichidagi `${...}` ni kengaytirmaydi.
Postgres paroli `.env` dan **o'zgarmaydi**: u faqat baza birinchi marta
yaratilganda o'rnatiladi, keyin `ALTER USER omruser PASSWORD '...'` kerak
(`docs/08` §8.1.1).

**8. Bash tool heredoc ichida `\n` ni buzadi.**
Python/TS satrlariga escape yozish kerak bo'lsa `Write`/`Edit` tool'ini
ishlating, `cat <<'EOF'` emas — `"\n"` haqiqiy qator uzilishiga aylanib
faylni sintaksis xatosiga olib keladi. Bu Markdown/shell'dagi `\` qator
davomiga ham tegishli — u ham yo'qoladi.

**9. `celery beat` ALOHIDA konteyner.**
`cleanup_temp_files` jadvali `worker/celery_app.py: beat_schedule` da, lekin
uni faqat `beat` servisi ishga tushiradi. Compose'da u bor; jadval o'zgarsa
`beat` ni ham qayta ishga tushiring.

**10. Bot/worker/beat'da healthcheck ATAYLAB o'chirilgan.**
Dockerfile'dagi `HEALTHCHECK` `/health` ga uradi — faqat `api` HTTP
tinglaydi. Boshqalarida compose'da `healthcheck: disable: true`; olib
tashlamang, aks holda ular doim "unhealthy" ko'rinadi.

**11. `/health` endi DB va Redis'ni ham tekshiradi va 503 qaytarishi mumkin.**
Faqat jarayon tirikligi kerak bo'lsa `GET /health?deep=false`.

**12. Admin tokenida `fam` (sessiya oilasi) claim bor.**
Refresh aylanganda `jti` o'zgaradi, `fam` qoladi; bekor qilish ro'yxati
Redis'da (`admin:revoked:*`). Redis yotsa tekshiruv **fail-open** — bu
ongli murosa (`services/token_store.py`).

**13. Fayl yo'llari ikki papkada.**
Skan `temp_dir` ga tushadi, baholangandan keyin worker uni `uploads_dir`
(`/data/uploads`, doimiy volume) ga KO'CHIRADI va `attempt.source_file` ni
yangilaydi. `temp_dir` ni kunlik `cleanup_temp_files` tozalaydi — review
fayllari u yerda qolib ketmasin.

---

## Sxema haqiqati (taxmin qilmang)

Nomlar "odatiy" nomlardan farq qiladi:

| Jadval | Haqiqiy ustunlar |
|---|---|
| `tests` | `question_count`, `variant_count`, `answer_key` (JSONB) — `q_count`/`opt_count`/`correct_keys` EMAS |
| `students` | `telegram_id` bor, `code` YO'Q |
| `attempts` | `detected`, `detail`, `percent`, `needs_review`, `source_file`, `debug_file`, `submitted_by_id` (004) — `raw_answers`/`percentage`/`debug_image_path` EMAS |
| `subscriptions` | `anchor_day` (004) — davr langari, `period_start.day` EMAS |

JSONB shakllari:

```
attempts.detected    = {"1": "A", "2": null, ...}
attempts.detail      = {"1": {"got": "A", "key": "A", "ok": true}, ...}
attempts.bubble_data = {"1": {"ratios": {"A": 0.91, ...}, "conf": 0.96,
                              "flag": null|"blank"|"ambiguous", "answer": "A"}}
tests.answer_key     = {"1": "A", ...}
```

`attempts.titul_id` **NULL bo'lishi mumkin** (QR hali o'qilmagan pending
skan). Skanlar ustidagi har qanday JOIN `outerjoin` bo'lishi shart — aks
holda aynan eng muammoli skanlar ro'yxatdan tushib qoladi.
Bunday skan uchun egalik **`attempts.submitted_by_id`** orqali aniqlanadi
(`services/access.py`) — zanjir uzilgan, boshqa belgi yo'q.

`confidence` va `bubble_data` faqat `003` dan keyingi skanlarda bor;
eskilarida NULL — UI buni ko'rsatishi kerak, yiqilmasligi kerak.

---

## SaaS qatlami (`003` migratsiya)

`plans`, `subscriptions`, `audit_logs`, `broadcasts`, `broadcast_recipients`.

**Tarif va sarf faqat `subscriptions` da.** `users.plan_id` / `users.quota_used`
ataylab YO'Q — dublikat ustunlar muqarrar bir-biriga mos kelmay qolardi.
`uq_subscriptions_active_user` (qisman unique indeks) bitta userda bitta
faol obunani bazaning o'zida kafolatlaydi.

- Kvota davri — **lazy rollover**: `ensure_period()` o'qish paytida davrni
  suradi. Cron yo'q, qidirmang.
- `NULL` limit = **cheksiz**. `0` = umuman ruxsat yo'q. Ikkisi boshqa ma'no.
- Skan hisobi **navbatga qo'yilganda** olinadi (natijadan qat'i nazar) —
  aks holda xato bergan varaqni qayta yuborib limitni aylanib o'tish mumkin.
- `ENFORCE_QUOTA=false` (standart) — limit hisoblanadi, lekin bloklanmaydi.

Rollar iyerarxik: `ANALYST` < `SUPPORT_OPERATOR` < `SUPERADMIN`.

---

## Konventsiyalar

- **Kod izohlari va foydalanuvchi matnlari — o'zbekcha.** Yangi kod ham
  shunday bo'lsin (mavjud fayllarga qarang).
- Pydantic v2, SQLAlchemy 2.0 `Mapped[...]` uslubi, `from __future__ import annotations`.
- Frontend: `@/` → `src/`, shadcn/ui primitivlari `components/ui/`,
  server-side pagination (`DataTable` + backend `Page[T]`).
- Grafik ranglari: `--series-1..3` (kategorik, tartibi o'zgarmaydi) va
  `--status-good/warning/critical` (holat). Ikkisi aralashtirilmaydi;
  status rangi "4-qator" sifatida ishlatilmaydi.
- **Egalik (tenant):** ustoz ma'lumotiga tegadigan har servis funksiyasi
  majburiy `owner_id` oladi (`None` = ataylab tenant'siz: ichki API, admin,
  worker). Bot handlerlari va `/api/web/*` obyektni `services/access.py`
  dagi `owned_*` orqali oladi; begona obyekt → "topilmadi"/404, 403 emas.
  Yangi callback yoki endpoint yozsangiz — shu qoida.
- Admin amali o'zgartiruvchi bo'lsa — `services/audit.record(...)` chaqiring.
- Telegram HTML xabarida foydalanuvchi matni — `services/telegram.escape()`.

---

## Chuqurroq hujjatlar (kerak bo'lgandagina o'qing)

| Fayl | Nima uchun |
|---|---|
| `docs/08_ADMIN_PANEL.md` | Admin panel: auth oqimi, endpointlar jadvali, setup, troubleshooting |
| `docs/03_OMR_PIPELINE.md` | OMR bosqichlari, anchor/bubble mantiqi |
| `docs/02_DATABASE.md` | Asl sxema (001/002 davri) |
| `weaknesses.md` | **Xavfsizlik auditi** — ish boshlashdan oldin ko'rib chiqing |

---

## Ma'lum muammolar

`weaknesses.md` dagi **37 banddan 37 tasi yopildi** (2026-09-19). Qolgani:

1. **Bot tokeni git tarixida.** `.env.example` dan olib tashlandi, lekin
   eski commitlarda qolgan va hozir ham ishlatilmoqda —
   **BotFather orqali revoke qilinishi kerak** (buni faqat odam qila oladi).
   CI har push'da git'dagi fayllarni token shabloniga tekshiradi.
   Git tarixini qayta yozish (`filter-repo`) — foydalanuvchi qarori.

**Ongli murosalar** (zaiflik emas, qabul qilingan cheklov — o'zgartirishdan
oldin foydalanuvchidan so'rang):

- **5 variantli test o'chirilgan** (T-21 varianti A). `omr/layout.py` da
  `options` faqat `"ABCD"`; bot 5 ni tanlashga ruxsat bermaydi, eski
  5-variantli testlarga ogohlantirish chiqadi. Layout'ga `E` qo'shish
  kalibrlash talab qiladi (`scripts/calibrate.py`, `docs/03`).
- **Ko'p sahifali PDF** — faqat 1-sahifa tekshiriladi, natija xabarida
  ogohlantirish bor. Har sahifani alohida urinish qilish — alohida feature.
- **HEIC rad etiladi** (OpenCV o'qiy olmaydi); foydalanuvchiga nima qilish
  kerakligi aytiladi.
- **O'quvchini botga ulash oqimi yozilmagan** — `students.telegram_id` va
  `link_telegram()` bor, handler yo'q (`docs/05` "Rejalashtirilgan").
- **Albom kollektori jarayon xotirasida** — bot restart bo'lsa yig'ilayotgan
  albom yo'qoladi; yetim fayllarni kunlik `cleanup_temp_files` o'chiradi.
- **Grafana alert kontakt nuqtasi repoda yo'q** (sir) — UI'da sozlanadi.
