# tasks.md — `weaknesses.md` dagi zaifliklarni tuzatish rejasi

Tuzilgan sana: 2026-09-16. Manba: `weaknesses.md` (2026-09-15 auditi).
Har bir band uchun kod **qayta tekshirildi** — audit yozilgandan keyin ba'zi
narsalar allaqachon tuzatilgan. Holat ustuni shu tekshiruv natijasi.

**FAZA 0, FAZA 1 va FAZA 2 bajarildi** (FAZA 2 — 2026-09-16). Endi sizning qo'lingizdagi ishlar (token revoke,
server `.env`, deploy, tekshirish) alohida faylda: **`QOLGAN_ISHLAR.md`**.

Bu fayl AI agent (Claude Code va sh.k.) yoki dasturchi uchun ish buyrug'i.
Har task mustaqil bajariladigan qilib yozilgan: muammo → aniq fayl/qator →
yechim qadamlari → qabul mezonlari → tekshirish usuli.

---

## 0. Agent uchun umumiy qoidalar (har taskdan oldin o'qing)

1. **Avval `CLAUDE.md` ni o'qing.** U yerdagi tuzoqlar (tz-aware datetime,
   bitta AsyncSession parallel emas, `selectinload` zanjiri, admin roli bazadan
   o'qiladi, rebuild kerakligi) shu tasklarda ham amal qiladi.
2. **Kod izohlari va foydalanuvchiga ko'rinadigan matnlar — o'zbekcha.**
3. **Model yoki `app/services/` o'zgarsa `docker compose build` (servis nomisiz)**
   — `api`, `bot`, `worker` alohida image; bittasini build qilsangiz qolganlari
   eski kodda qoladi.
4. **Har taskdan keyin testlar:**
   ```bash
   docker compose run --rm --no-deps api pytest app/tests -q
   ```
   Frontend tegilsa: `cd admin-ui && npm run typecheck && npm run build`.
5. **Telegram HTML xabarida foydalanuvchi matni** → `app/services/telegram.py:escape()`.
   Bot `DefaultBotProperties(parse_mode=HTML)` bilan ishga tushgan
   (`app/bot/main.py:29`), ya'ni `parse_mode` berilmagan xabarlar ham HTML.
6. **Admin amali o'zgartiruvchi bo'lsa** → `services/audit.record(...)`.
7. **Bitta task = bitta commit** (iloji boricha). Commit xabari: `fix(T-XX): ...`.
8. **Foydalanuvchi qarori kerak bo'lgan tasklar** (T-21, T-24 B varianti, T-25
   HEIC) — bajarishdan oldin so'rang; ular alohida bo'limda belgilangan.
9. Fayl yo'llari `app/...` — repo ildizidan. Qator raqamlari 2026-09-16 holatiga;
   o'zgargan bo'lsa funksiya nomi bo'yicha qidiring.
10. Bash heredoc ichida `\n` buziladi — Python/TS satr yozishda `Write`/`Edit`
    tool ishlating.

Holat belgilari: ❌ ochiq · 🟡 qisman tuzatilgan · ✅ tuzatilgan (task yo'q yoki faqat qoldiq).

---

## 1. Zaiflik → task xaritasi (2026-09-16 tekshiruvi)

| № | Zaiflik (qisqa) | Holat | Task |
|---|---|---|---|
| 1 | Bot tokeni `.env.example` da va git tarixida | ✅ fayldan olindi + CI skani; **revoke odam zimmasida** | T-01 |
| 2 | `/api/web/*` tenant izolyatsiyasi yo'q | ✅ har endpoint `user.id` bilan | T-07 |
| 3 | Bot callback'larida egalik tekshiruvi yo'q | ✅ handler + servis (`owner_id`) | T-08 |
| 4 | `/static/*` auth'siz, PDF nomi ketma-ket | ✅ mount yo'q, auth'li fayl endpointlari, PDF nomi UUID | T-10 |
| 5 | Default maxfiy kalitlar | ✅ ikkalasi ham himoyalangan | T-02 |
| 6 | Docker portlari ochiq, Redis parolsiz | ✅ hammasi 127.0.0.1 + Redis parol | T-03 |
| 7 | `.dockerignore` / `.env` image'da / root / `--reload` | ✅ | T-04 |
| 8 | Deploy tartibi (migratsiya keyin) | ✅ migratsiya oldin + CI testlar | T-05 |
| 9 | `/attempts/scan` buzuq | ❌ | T-26 |
| 10 | Kvota/blok chaqirilmaydi | ✅ skan/guruh/o'quvchi limitlari, `/start`'da obuna, middleware ro'yxat+blok | T-09 ✅, T-17 ✅ |
| 11 | FSM matn bo'lmagan xabarda yiqiladi | ✅ `F.text` + `fsm_non_text` fallback, skan `StateFilter(None)` | T-11 ✅ |
| 12 | 5 variant ishlamaydi | ❌ | T-21 (qaror kerak) |
| 13 | 180° burilgan varaq | ❌ | T-20 |
| 14 | Worker resurs DoS | ❌ | T-18 |
| 15 | `omr_task` xato oqimi / `bubble_data` | 🟡 `bubble_data`/`confidence` yoziladi (`tasks.py:346`); xabar+retry hali bor | T-19 |
| 16 | Telegram HTML injection | ✅ `escape()` hamma joyda | T-12 ✅ |
| 17 | Excel/CSV formula injection | ✅ `safe_cell`/`safe_filename` | T-13 ✅ |
| 18 | Obuna muddati tugamaydi | 🟡 `ends_at` tekshiriladi (`subscriptions.py:166`), `scans_used` ko'chmaydi; faqat davr siljishi qoldi | T-39 (past) |
| 19 | Admin OTP oqimi | 🟡 enumeratsiya tuzatilgan; IP limit, XFF, refresh rotatsiya, logout yo'q | T-30 |
| 20 | initData replay | ❌ | T-28 |
| 21 | CORS `*`+credentials, `/docs` ochiq | 🟡 CORS tuzatilgan (`main.py:43-59`); `/docs` ochiq | T-29 |
| 22 | Telegram flood (titul yuborish) | ❌ | T-24 |
| 23 | Ko'p sahifali PDF | ❌ | T-18 |
| 24 | Qo'lda tuzatish nomuvofiq | 🟡 admin `override_answers` to'g'ri; `web_api` va `PATCH /attempts` emas | T-27 |
| 25 | O'lik UI | ✅ `results:` handler, reply.py o'chirildi, `telegram_id` UI'dan olindi | T-14 ✅ |
| 26 | Foydalanuvchi ma'lumoti eskiradi | ✅ middleware yaratadi/yangilaydi, handlerlar `db_user` oladi | T-15 ✅ |
| 27 | `parse_key` takror raqam | ✅ | T-16 ✅ |
| 28 | Timezone | 🟡 naive tuzatilgan; "bugun" UTC bo'yicha | T-32 |
| 29 | `get_db` har GET'da commit | ❌ | T-33 |
| 30 | Skan qabul nozikliklari | ❌ | T-25 |
| 31 | Loki handler chegarasiz | ❌ | T-34 |
| 32 | Celery natijalari saqlanadi | ❌ | T-23 |
| 33 | `fill_ratio` sekin | ❌ | T-22 |
| 34 | Testlar real bazaga yozadi | ❌ (`test_web_api.py`) | T-35 |
| 35 | Admin API yarim / `ilike` escape | 🟡 router ulangan; `ilike` escape yo'q (6 joy) | T-31 |
| 36 | Docs/kod nomuvofiqligi | ❌ | T-36 |
| 37 | Past: Dockerfile, scratch, `attempts.user_id`, backup, metrik | ❌ | T-04, T-37, T-38 |

---

## 2. Bajarish tartibi

```
FAZA 0 (darhol, 1 kun):     T-01 → T-02 → T-03 → T-04 → T-05
FAZA 1 (xavfsizlik, 2-3 kun): T-06 → T-07 → T-08 → T-09 → T-10
FAZA 2 (bot barqarorligi):  T-11 → T-12 → T-13 → T-14 → T-15 → T-16 → T-17
FAZA 3 (worker/OMR):        T-18 → T-19 → T-23 → T-22 → T-25 → T-24 → T-20 → T-21
FAZA 4 (API/admin):         T-26 → T-27 → T-28 → T-29 → T-31 → T-32 → T-30 → T-33 → T-34
FAZA 5 (sifat):             T-35 → T-36 → T-37 → T-38 → T-39
```

T-06 (egalik helperlari) T-07/T-08/T-09/T-10 uchun asos — birinchi bajariladi.
T-35 (test izolyatsiyasi) T-05 dagi CI pytest qadamiga kerak; T-05 ni avval
"faqat DB'siz testlar" bilan qilib, T-35 dan keyin to'liq yoqish mumkin.

---

# FAZA 0 — Darhol (sirlar va infra)

## T-01 · Bot tokenini revoke qilish va `.env.example` ni tozalash

**✅ BAJARILDI (2026-09-16)** — `.env.example` tozalandi, CI'ga token skani qo'shildi.
**QOLDI (odam):** BotFather orqali eski tokenni revoke qilish; git tarixini
qayta yozish (foydalanuvchi qarori).

- **Zaiflik:** №1 · **Prioritet:** 🔴 KRITIK · **Hajm:** S · **Bog'liqlik:** yo'q
- **Holat:** ❌ `.env.example:8` da haqiqiy token turibdi (tekshirildi), git
  tarixida `591d758` dan beri.

**Muammo.** Repo'ni ko'rgan har kim botni to'liq boshqaradi (xabar o'qish,
foydalanuvchilarga yozish, Mini App `initData` imzosini soxtalash — chunki
`validate_init_data` HMAC kaliti aynan `bot_token`).

**Yechim (qadamlar).**
1. **Odam bajaradi (agent qila olmaydi):** BotFather → `/mybots` → bot →
   *API Token* → *Revoke current token*. Yangi tokenni faqat serverdagi `.env`
   ga yozing.
2. `.env.example` da:
   ```
   BOT_TOKEN=123456789:REPLACE_WITH_TOKEN_FROM_BOTFATHER
   ```
   Xuddi shu faylda `INTERNAL_API_KEY`, `SECRET_KEY`, `POSTGRES_PASSWORD`,
   `DATABASE_URL`/`SYNC_DATABASE_URL` ichidagi parol ham namunaviy ekani aniq
   yozilsin (`CHANGE_ME_...`). Sarlavhadagi "hammasini to'ldiring" jumlasi
   qoladi — endi u to'g'ri.
3. Git tarixini tozalash **ixtiyoriy** (`git filter-repo`), chunki token
   revoke qilingach tarixdagi nusxa foydasiz. Tarix qayta yozilsa barcha
   klonlar sinadi — foydalanuvchi bilan kelishing.
4. `README.md` / `docs/08_ADMIN_PANEL.md` "Setup" bo'limiga: "Tokenni hech
   qachon `.env.example` ga yozmang" eslatmasi.
5. Kelajak uchun: `.github/workflows/` ga `gitleaks` yoki oddiy grep tekshiruvi
   (`\d{8,}:[A-Za-z0-9_-]{35}` pattern) — token commit qilinsa CI yiqilsin.

**Qabul mezonlari.**
- `grep -E '[0-9]{8,}:[A-Za-z0-9_-]{35}' .env.example` hech narsa topmaydi.
- Eski token bilan `https://api.telegram.org/bot<OLD>/getMe` → 401.

---

## T-02 · `INTERNAL_API_KEY` default tekshiruvi va doimiy vaqtli solishtirish

**✅ BAJARILDI (2026-09-16)** — `assert_internal_key_is_safe()`, `compare_digest`,
startup ogohlantirishi, 5 ta yangi test.

- **Zaiflik:** №5, №37 · **Prioritet:** 🔴 · **Hajm:** S
- **Holat:** 🟡 `SECRET_KEY` uchun `core/security.py:assert_secret_is_safe()`
  bor. `internal_api_key="change-me"` (`config.py:44`) uchun hech qanday
  tekshiruv yo'q; `api/deps.py:13` oddiy `!=` bilan solishtiradi.

**Yechim.**
1. `app/core/security.py` ga `_INSECURE_SECRETS` ro'yxatiga
   `"change-me-super-secret-internal-key"` qo'shing va yangi funksiya:
   ```python
   def assert_internal_key_is_safe() -> None:
       key = get_settings().internal_api_key
       if key in _INSECURE_SECRETS or len(key) < 24:
           raise InsecureSecretError("INTERNAL_API_KEY namunaviy yoki qisqa ...")
   ```
2. `app/api/deps.py:verify_internal_key`:
   ```python
   import hmac
   try:
       assert_internal_key_is_safe()
   except InsecureSecretError as exc:
       raise HTTPException(503, detail=str(exc))
   if not hmac.compare_digest(x_internal_key, get_settings().internal_api_key):
       raise HTTPException(403, ...)
   ```
3. `app/api/main.py:lifespan` da ishga tushganda ikkala kalitni tekshirib
   **faqat log'ga ERROR** yozing (yiqitmang — bot/Mini App ishlashi kerak):
   ```python
   for check in (assert_secret_is_safe, assert_internal_key_is_safe):
       try: check()
       except InsecureSecretError as exc: log.error("XAVFSIZLIK: %s", exc)
   ```
4. `app/tests/test_admin_security.py` ga `INTERNAL_API_KEY="change-me"` bilan
   `/attempts/1` → 503 testi.

**Qabul mezonlari.** Namunaviy kalit bilan `/attempts/*` 503 qaytaradi;
to'g'ri kalit bilan ishlaydi; `pytest` yashil.

---

## T-03 · Docker portlarini yopish, Redis'ga parol

**✅ BAJARILDI (2026-09-16)** — barcha portlar `127.0.0.1`, Redis/Grafana parol
majburiy, `API_BIND_HOST` bilan boshqariladi.

- **Zaiflik:** №6 · **Prioritet:** 🔴 · **Hajm:** S
- **Holat:** ❌ `docker-compose.yml`: postgres `5433`, redis `6380`, api
  `8000`, loki `3100`, grafana `3001`, flower `5555` — hammasi `0.0.0.0`.

**Yechim.**
1. Har `ports:` ni `127.0.0.1:` ga bog'lang:
   ```yaml
   ports:
     - "127.0.0.1:5433:5432"
   ```
   API uchun ham `127.0.0.1:8000:8000` — serverda nginx/caddy reverse proxy
   turadi deb hisoblanadi (WEB_APP_URL HTTPS bo'lishi shart, demak proxy bor).
   Agar proxy yo'q bo'lsa — foydalanuvchidan so'rang.
2. Redis parol:
   ```yaml
   redis:
     command: redis-server --appendonly yes --requirepass ${REDIS_PASSWORD}
     healthcheck:
       test: ["CMD", "redis-cli", "-a", "${REDIS_PASSWORD}", "ping"]
   ```
   `.env.example`: `REDIS_PASSWORD=CHANGE_ME` va
   `REDIS_URL=redis://:${REDIS_PASSWORD}@redis:6379/0` (compose `env_file`
   `${}` ni kengaytirmaydi — `.env` da to'liq URL yozilsin, `.env.example` da
   izoh bilan).
   `REDIS_URL` ishlatiladigan joylar: `config.py:40`, `bot/main.py:33`
   (FSM), `celery_app.py:14-15`, `admin/auth.py:76` (OTP) — hammasi
   `settings.redis_url` dan oladi, kod o'zgarmaydi.
3. Grafana: `GF_SECURITY_ADMIN_PASSWORD=${GRAFANA_ADMIN_PASSWORD}`.
4. Loki/Grafana/Flower'ni `profiles: [monitoring]` ostiga o'tkazing — default
   `up -d` da ko'tarilmasin.

**Qabul mezonlari.** `docker compose config | grep -E '^\s+- "0\.0\.0\.0|^\s+- "[0-9]'`
bo'sh; `redis-cli -h 127.0.0.1 -p 6380 ping` → `NOAUTH`; bot/worker/api
Redis'ga ulanadi (loglarda xato yo'q).

---

## T-04 · `.dockerignore` ga `.env`, non-root user, `--reload` ni olib tashlash, HEALTHCHECK

**✅ BAJARILDI (2026-09-16)** — `.env` image'dan chiqarildi, `appuser` (uid 10001)
+ `docker/entrypoint.sh`, `--reload` olib tashlandi, api healthcheck, `INSTALL_DEV`.

- **Zaiflik:** №7, №37 · **Prioritet:** 🔴 · **Hajm:** S
- **Holat:** 🟡 `.dockerignore` mavjud (`.git`, `scratch`, `node_modules`
  bor) lekin **`.env` yo'q** → `COPY . .` (`Dockerfile:59`) `.env` ni
  image'ga oladi. Container `root`. Compose `api` `--reload` bilan
  (`docker-compose.yml:59`). `pip install -e ".[dev]"` — prod'da dev-deps.

**Yechim.**
1. `.dockerignore` ga qo'shing: `.env`, `.env.*`, `!.env.example`, `docs`,
   `*.md`, `tasks.md`, `weaknesses.md`, `.github`, `admin-ui/.env*`.
2. `Dockerfile`:
   - `RUN useradd -r -u 10001 -m appuser` ; `RUN mkdir -p /data/pdfs /data/debug /tmp/omr_uploads && chown -R appuser /data /tmp/omr_uploads /app`; oxirida `USER appuser`.
   - Compose'dagi named volume'lar root bilan yaratiladi — `chown` build'da
     yetmaydi. Yechim: har servisga `user: "10001:10001"` **yoki**
     entrypoint skripti (`gosu`). Eng sodda: volume'larga `driver_opts` emas,
     balki ilova ishga tushganda `settings.ensure_dirs()` allaqachon
     `mkdir` qiladi — `USER appuser` bilan `/data/*` yozib bo'lmasa
     `PermissionError` chiqadi. Shuning uchun compose'da:
     ```yaml
     x-app-base:
       user: "10001:10001"
     ```
     va birinchi ishga tushirishda `docker compose run --rm --user root api chown -R 10001:10001 /data /tmp/omr_uploads`
     — buni `docs/08` "Setup" ga yozing.
   - `pip install -e "."` (dev-deps'siz); testlar uchun alohida
     `docker compose run --rm api pip install -e ".[dev]" && pytest` yoki
     `Dockerfile` da `ARG INSTALL_DEV=false`.
   - `HEALTHCHECK CMD curl -f http://localhost:8000/health || exit 1`
     (`curl` apt ro'yxatiga) — faqat api uchun mantiqiy; compose `api`
     servisiga `healthcheck` yozing.
3. `docker-compose.yml` `api.command` dan `--reload` ni olib tashlang.
   Dev uchun `docker-compose.override.yml` (git'da `*.override.yml` ignore)
   namunasini `docs/08` ga yozing: `command: ... --reload` + source volume.
4. `uvicorn` ga `--proxy-headers --forwarded-allow-ips=<proxy_ip>` (T-30 ga
   kerak, hozir qo'shib qo'ying; qiymatni `.env` `TRUSTED_PROXY_IPS` dan).

**Qabul mezonlari.** `docker compose build && docker compose run --rm api sh -c 'ls -la /app/.env; id'`
→ `.env` yo'q, `uid=10001`; PDF generatsiya va skan yozish ishlaydi
(volume'lar yozilishi tekshirildi).

---

## T-05 · Deploy: migratsiya konteynerlardan OLDIN, CI'da test

**✅ BAJARILDI (2026-09-16)** — `test` job (image build + migratsiya + pytest +
admin-ui build + token skani), deploy `needs: test`, migratsiya `up -d` dan oldin.

- **Zaiflik:** №8 · **Prioritet:** 🔴 · **Hajm:** S
- **Holat:** ❌ `.github/workflows/deploy.yml:48-51`: `up -d --build` →
  keyin `alembic upgrade`. Yangi kod eski sxemada `admin_role` ni SELECT
  qiladi → migratsiya tugaguncha 500/crash.

**Yechim.**
1. SSH skriptini quyidagi tartibga keltiring:
   ```bash
   cd /var/www/omr-test-bot
   git pull origin main
   docker compose build                                  # hamma image
   docker compose run --rm --no-deps api alembic upgrade head   # YANGI image, eski konteynerlar ishlayapti
   docker compose up -d api bot worker                   # endi yangi kod
   docker compose ps
   docker image prune -f
   ```
   Additiv migratsiyalar (ustun qo'shish) eski kod bilan mos — shu sababli
   avval migratsiya xavfsiz. Ustun **o'chiradigan** migratsiya bo'lsa ikki
   bosqichli deploy kerak — `docs/08` ga eslatma.
2. `docker-compose` (defis) → `docker compose` (v2) — serverda qaysi biri
   borligini foydalanuvchidan so'rang yoki ikkalasini `command -v` bilan tanlang.
3. Yangi job `test` (deploy'dan oldin, `needs: test`):
   ```yaml
   test:
     runs-on: ubuntu-latest
     services:
       postgres: { image: postgres:16-alpine, env: {POSTGRES_USER: omruser, POSTGRES_PASSWORD: omrpass, POSTGRES_DB: omrdb_test}, ports: ["5432:5432"], options: --health-cmd pg_isready ... }
       redis: { image: redis:7-alpine, ports: ["6379:6379"] }
     steps:
       - uses: actions/checkout@v4
       - uses: actions/setup-python@v5  (python 3.11)
       - run: sudo apt-get install -y libzbar0 libpango-1.0-0 libpangocairo-1.0-0 libcairo2 libgdk-pixbuf-xlib-2.0-0
       - run: pip install -e ".[dev]"
       - run: alembic upgrade head        # DATABASE_URL env bilan
       - run: pytest app/tests -q
     env: { BOT_TOKEN: "1:test", DATABASE_URL: postgresql+asyncpg://omruser:omrpass@localhost:5432/omrdb_test, SYNC_DATABASE_URL: ..., SECRET_KEY: <64 hex>, INTERNAL_API_KEY: <32 belgi>, REDIS_URL: redis://localhost:6379/0 }
   ```
   T-35 bajarilmaguncha `test_web_api.py` real bazaga yozadi — CI'da bu
   alohida test bazasi bo'lgani uchun muammo emas.
4. Rollback bo'limi `docs/08` ga: `git checkout <prev_sha> && docker compose build && alembic downgrade -1 && up -d`.

**Qabul mezonlari.** Workflow'da `test` job deploy'dan oldin; SSH skriptida
`alembic upgrade head` `up -d` dan oldin.

---

# FAZA 1 — Tenant izolyatsiyasi (IDOR)

## T-06 · Egalik tekshiruvi helperlari (`app/services/access.py`)

**✅ BAJARILDI (2026-09-16)** — `owned_group/test/student/titul/attempt` + `owner_filter_for_*`;
servislar (`get_tests_by_group`, `get_students_by_group`, `get_tituls_by_test`,
`generate_tituls_for_test`, `export_*_excel`) majburiy `owner_id` oladi (`None` = tenant'siz).

- **Asos task:** T-07, T-08, T-09, T-10 shundan foydalanadi · **Hajm:** S

**Yechim.** Yangi modul `app/services/access.py`:
```python
"""Egalik (tenant) tekshiruvlari — bot va web API uchun yagona manba.
Har funksiya obyektni FAQAT egasi uchun qaytaradi, aks holda None."""
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from app.models import Group, Test, Student, Titul, Attempt

async def owned_group(db, group_id: int, owner_id: int) -> Group | None:
    return (await db.execute(select(Group).where(Group.id == group_id, Group.owner_id == owner_id))).scalar_one_or_none()

async def owned_test(db, test_id: int, owner_id: int) -> Test | None:
    stmt = select(Test).join(Group, Group.id == Test.group_id).where(Test.id == test_id, Group.owner_id == owner_id).options(selectinload(Test.group))
    ...

async def owned_student(db, student_id: int, owner_id: int) -> Student | None:  # Student → Group.owner_id
async def owned_attempt(db, attempt_id: int, owner_id: int) -> Attempt | None:
    # Attempt → Titul → Test → Group.owner_id; selectinload zanjiri OXIRIGACHA
    # (CLAUDE.md tuzoq 4). titul_id NULL bo'lgan pending skan hech kimga
    # tegishli emas → None (yoki T-37 dan keyin submitted_by_id bo'yicha).
```
`services/groups.py:get_group_for_owner` allaqachon bor — uni shu modulga
ko'chiring yoki `owned_group` uni chaqirsin (dublikat qoldirmang).

Testlar: `app/tests/test_access.py` — ikki ustoz, biri ikkinchisining
obyektini so'raydi → `None`. (T-35 gacha DB kerak; hozircha `test_web_api`
uslubida yozing, keyin T-35 fixture'ga o'tkaziladi.)

---

## T-07 · `/api/web/*` da tenant izolyatsiyasi

**✅ BAJARILDI (2026-09-16)** — 7 endpoint + yangi fayl endpointi `user.id` bilan; begona → 404.
T-27 validatsiyasi (harf/savol tekshiruvi, `manual_override`) FAZA 4 da qoladi.

- **Zaiflik:** №2 · **Prioritet:** 🔴 KRITIK · **Hajm:** M · **Bog'liqlik:** T-06
- **Holat:** ❌ `app/api/routes/web_api.py` — router `dependencies=[Depends(get_webapp_user)]`
  (`:32`) faqat autentifikatsiya; `user` hech bir endpointda yo'q.

**Muammo.** Istalgan ro'yxatdan o'tgan ustoz boshqa ustozning guruhlari
(`:87`), o'quvchilari (`:113`), **javob kalitlari** (`:155`, `answer_key`
`:232`), natijalari (`:241`, `:293`) ni ko'radi va **istalgan attempt
bahosini o'zgartiradi** (`:354`). `dashboard-stats` (`:47`) butun tizim
statistikasini beradi.

**Yechim.** Har endpointga `user: User = Depends(get_webapp_user)` qo'shib,
so'rovni `user.id` bo'yicha cheklang:

| Endpoint | O'zgarish |
|---|---|
| `GET /dashboard-stats` | Har `count`/`avg` ga `Group.owner_id == user.id` join. `Attempt` uchun: `Attempt → Titul → Test → Group` join (outerjoin shart emas — statistika faqat bog'langanlar uchun). |
| `GET /groups` | `.where(Group.owner_id == user.id)` |
| `GET /groups/{id}` | `owned_group(db, group_id, user.id)` → None bo'lsa **404** (403 emas — mavjudligini oshkor qilmaslik uchun) |
| `GET /tests/{id}` | `owned_test(...)`; `history_svc.test_results/test_stats` o'zgarmaydi (test allaqachon tekshirilgan) |
| `GET /students/{id}` | `owned_student(...)` |
| `GET /attempts/{id}` | `owned_attempt(...)` |
| `POST /attempts/{id}/review` | `owned_attempt(...)` + T-27 dagi validatsiya |

`get_webapp_user` ikki marta chaqirilmasin: router darajasidagi
`dependencies=[...]` ni olib tashlang (endi har endpoint o'zi oladi).
FastAPI dependency'ni bitta so'rovda kesh qiladi, lekin tozalik uchun.

**Testlar.** `test_web_api.py` ga: ikkinchi `User` (telegram_id=999998)
yaratib `app.dependency_overrides[get_webapp_user]` ni unga o'rnatib, birinchi
ustozning `/groups/{id}`, `/tests/{id}`, `/attempts/{id}`,
`/attempts/{id}/review` → 404; `/groups` → bo'sh ro'yxat; `/dashboard-stats`
→ nol.

**Qabul mezonlari.** Yuqoridagi testlar yashil; `grep -n "Depends(get_db)" app/api/routes/web_api.py`
dagi har endpointda `user` parametri bor.

---

## T-08 · Bot callback'larida egalik tekshiruvi

**✅ BAJARILDI (2026-09-16)** — groups/students/tests/results handlerlari `owned_*` bilan;
FSM `group_id`/`test_id` qayta tekshiriladi; `_owner_id` dublikatlari → `bot/common.owner_id_for`.

- **Zaiflik:** №3 · **Prioritet:** 🔴 KRITIK · **Hajm:** M · **Bog'liqlik:** T-06
- **Holat:** ❌ Faqat `del_group` (`groups.py:125`) va `menu_*` to'g'ri.

**Muammo.** Callback data (`group:5`, `test:12`, `res_student_excel:77`)
mijoz tomonidan yuboriladi — istalgan ID qo'yish mumkin. Tekshirilmagan
handlerlar:

| Fayl | Handler | Callback | Obyekt |
|---|---|---|---|
| `groups.py:62` | `group_selected` | `group:` | Group |
| `students.py:18` | `list_students_handler` | `students:` | Group |
| `students.py:45` | `start_add_students` | `add_students:` | Group (FSM'ga `group_id` yoziladi) |
| `tests.py:72` | `list_tests_for_group` | `list_tests:` | Group |
| `tests.py:100` | `start_create_test` | `create_test:` | Group (FSM) |
| `tests.py:250` | `gen_tituls_all` | `gen_tituls:all` | FSM `test_id` — `tituls:` (`:315`) orqali tekshiruvsiz yozilgan |
| `tests.py:292` | `test_selected` | `test:` | Test |
| `tests.py:315` | `show_tituls_menu` | `tituls:` | Test |
| `tests.py:338`, `:364` | `send_tituls_single/zip` | `tituls_send:*:` | Test → **PDF (F.I.Sh + QR) chiqib ketadi** |
| `results.py:125` | `show_res_group` | `res_group:` | Group |
| `results.py:144` | `show_res_group_tests` | `res_group_tests:` | Group |
| `results.py:166`, `:193` | `show_res_test*` | `res_test*:` | Test |
| `results.py:247` | `show_res_student_tests` | `res_student_tests:` | Student |
| `results.py:289` | `show_res_attempt_detail` | `res_attempt_detail:` | Attempt |
| `results.py:347`, `:366`, `:385` | `export_*` | `res_*_excel:` | Group/Test/Student → **Excel chiqib ketadi** |

**Yechim.**
1. Har handlerda `owner_id = await _owner_id(call.from_user.id)` (allaqachon
   mavjud helper) va T-06 helperlari:
   ```python
   group = await owned_group(db, group_id, owner_id)
   if group is None:
       await call.answer("Guruh topilmadi.", show_alert=True)   # 403 emas — bir xil xabar
       return
   ```
2. Servis darajasida ham: `get_tests_by_group`, `get_students_by_group`,
   `get_tituls_by_test`, `export_group_excel`, `export_test_excel`,
   `export_student_excel` — bularga `owner_id` parametri qo'shib SQL'da
   `Group.owner_id == owner_id` join qiling. Handler unutsa ham servis
   himoya qiladi (ikki qatlam).
3. FSM'dagi `group_id`/`test_id` ishlatiladigan joylarda (`students.py:67`,
   `tests.py:207`, `tests.py:253`) ham qayta tekshiring — state Redis'da,
   lekin tekshirilmagan callback'dan yozilgan bo'lishi mumkin.
4. `_owner_id` helper uchta faylda takrorlangan (`groups.py:29`,
   `tests.py:38`, `results.py:43`) — `AccessMiddleware` `data["db_user"]`
   beradi (`middlewares/access.py:78`); handler imzosiga `db_user: User`
   qo'shib undan `db_user.id` oling (T-15 bilan birga). Ro'yxatdan o'tmagan
   (`db_user` yo'q) callback → `"/start yuboring"`.

**Testlar.** Handler unit-testi qiyin (aiogram). Minimal: `app/tests/test_access.py`
servis darajasida (`get_tests_by_group(db, gid, owner_id=other)` → `[]`).
Qo'lda: ikki Telegram akkaunt, birinchisining `test:<id>` callback'ini
ikkinchisidan yuborish (Telegram Desktop → bot'ga soxta callback yuborib
bo'lmaydi; `curl` bilan `answerCallbackQuery` emas — bu tekshiruvni servis
testiga qoldiring).

**Qabul mezonlari.** Yuqoridagi jadvaldagi har handlerda egalik tekshiruvi;
servislarda `owner_id` parametri majburiy.

---

## T-09 · Skan egaligi: faqat titul egasi skan qila oladi, ro'yxatsiz foydalanuvchi rad etiladi

**✅ BAJARILDI (2026-09-16)** — `scan.py` `db_user` yo'q bo'lsa rad; worker `_chat_owns_test`
pre-scan va pipeline'dan keyin (ikki qatlam). Ro'yxat siyosati: `/start` bosmagan → rad (T-15 da qayta ko'riladi).

- **Zaiflik:** №10 (qoldiq), №4 (QR bilan soxta skan) · **Prioritet:** 🔴 · **Hajm:** M
- **Holat:** ❌ `scan.py:65-68` — user yo'q bo'lsa kvota tekshiruvi
  o'tkazib yuboriladi va skan **baribir navbatga qo'yiladi** (`:97-100`
  `owner is None` → consume yo'q). `omr_task` (`tasks.py:326-368`) natijani
  `chat_id` ga yuboradi — titul kimniki ekanini tekshirmaydi. Demak QR
  nusxasiga ega **har kim** (o'quvchi ham) boshqa ustozning varag'ini skan
  qilib natijani oladi va `attempts` ga yozadi.

**Yechim.**
1. `scan.py` `handle_photo`/`handle_document`: `db_user: User | None = None`
   parametr (middleware beradi). `None` bo'lsa:
   `"Avval /start buyrug'ini yuboring."` va return. `_check_quota` /
   `_enqueue_scan` dagi `user is None` shoxlarini olib tashlang.
2. `omr_task` da titul topilgach (`tasks.py:311-324`):
   ```python
   owner_tg = db.execute(
       sa_select(User.telegram_id).join(Group, Group.owner_id == User.id)
       .join(Test, Test.group_id == Group.id).where(Test.id == titul.test_id)
   ).scalar_one_or_none()
   if owner_tg != chat_id:
       attempt.status = "error"; attempt.error_msg = "Titul boshqa ustozga tegishli"
       db.commit(); _send_message_sync(chat_id, "Bu varaq sizning testingizga tegishli emas."); return
   ```
   Bu tekshiruv 1-bosqich (`pre_titul`, `:229-231`) da ham qilinsa OMR
   umuman ishlamaydi — CPU tejaladi. Ikkalasida ham qiling.
3. `attempts` ga kim yuborganini yozish — T-37 (`submitted_by_id`). Bu task
   T-37 siz ham ishlaydi (`chat_id` task argumentida).
4. `_process_album` ham `db_user` bilan (album `chat_id` orqali user'ni
   qayta topadi — `handle_photo` da `db_user.id` ni `_album_collector` ga
   birga saqlang).

**Qabul mezonlari.** Ro'yxatsiz akkauntdan rasm → "/start yuboring", `attempts`
ga yozuv yo'q. Boshqa ustoz titulini skan → error attempt + xabar, natija
chiqmaydi. `test_access.py` ga worker tekshiruvi uchun sync-session testi.

---

## T-10 · Statik mountlarni olib tashlash, auth'li fayl endpointlari, PDF nomiga UUID

**✅ BAJARILDI (2026-09-16)** — mount'lar olib tashlandi; `services/attempt_files.py`;
`/api/web/attempts/{id}/file/{kind}` va `/api/admin/scans/{id}/file/{kind}`; dashboard.html va
OmrInspectorModal fetch+blob ga o'tdi (`npm run typecheck && build` toza); PDF nomi `titul_{uuid}.pdf`.

- **Zaiflik:** №4 · **Prioritet:** 🔴 KRITIK · **Hajm:** L · **Bog'liqlik:** T-06, T-07
- **Holat:** ❌ `app/api/main.py:62-64` uchta `StaticFiles` mount. PDF nomi
  `titul_{titul.id}_{student.id}.pdf` (`worker/tasks.py:138-141`).
  URL ishlatuvchilar: `web_api.py:310-311` (Mini App), `admin/scans.py:362-363`
  (`_static_url`), frontendlar `app/templates/dashboard.html:1056-1057` va
  `admin-ui/src/features/scans/OmrInspectorModal.tsx:183-184` (`<img src>`).

**Muammo.** `/static/pdfs/titul_1_1.pdf ... titul_9999_9999.pdf` — barcha
o'quvchilar titullari (F.I.Sh + QR) enumeratsiya qilinadi. `/static/uploads`
— o'quvchilar skanlari, `/static/debug` — annotatsiyalar.

**Yechim.**
1. **Mountlarni olib tashlang** (`main.py:62-64`). `/static/pdfs` ni hech kim
   URL orqali ishlatmaydi (PDF bot orqali `FSInputFile` bilan yuboriladi) —
   tekshirildi: `grep -rn "static/pdfs" app admin-ui/src` faqat `main.py`.
2. **Mini App uchun** `web_api.py` ga:
   ```python
   @router.get("/attempts/{attempt_id}/file/{kind}")   # kind: source | debug
   async def attempt_file(attempt_id, kind: Literal["source","debug"], user=Depends(get_webapp_user), db=...):
       attempt = await owned_attempt(db, attempt_id, user.id) or 404
       path = attempt.source_file if kind == "source" else attempt.debug_file
       if not path or not Path(path).is_file(): 404
       # Yo'l faqat ruxsat etilgan papkalar ichida bo'lsin (path traversal):
       assert Path(path).resolve().is_relative_to(settings.temp_dir.resolve()) or ... debug_output_dir
       return FileResponse(path, media_type="image/jpeg", headers={"Cache-Control": "private, max-age=300"})
   ```
   `get_attempt_details` javobida `source_url = f"/api/web/attempts/{id}/file/source"`.
3. **Admin uchun** `admin/scans.py` ga xuddi shunday
   `GET /api/admin/scans/{id}/file/{kind}` (`require_analyst`), `_static_url`
   o'rniga.
4. **Frontend — `<img src>` header yubora olmaydi.** Ikkala frontend ham
   `fetch` + `Authorization` + `URL.createObjectURL(blob)` ga o'tsin:
   - `dashboard.html:1056` atrofida: `fetch(url, {headers: {Authorization: 'tma ' + initData}})` → blob → `img.src`.
   - `OmrInspectorModal.tsx:183`: `client.ts` axios instance bilan
     `responseType: 'blob'`; `useEffect` ichida objectURL yaratib, unmount'da
     `revokeObjectURL`.
   Muqobil (agar `<img src>` saqlash zarur bo'lsa): qisqa muddatli imzolangan
   URL (`?exp=&sig=HMAC(secret_key, f"{kind}:{id}:{exp}")`). Kamchiligi:
   `SECRET_KEY` namunaviy bo'lsa Mini App ham ishlamay qoladi. **Tavsiya:
   fetch+blob.**
5. **PDF nomi:** `tasks.py:138-141` → `f"titul_{titul.uuid}.pdf"`. Eski
   fayllar joyida qoladi (`titul.pdf_path` bazada) — muammo yo'q, chunki mount
   olib tashlangan.
6. `schemas/admin/scans.py:93,96` description'larini yangilang.
7. `docs/08` endpoint jadvaliga ikki yangi endpoint.

**Qabul mezonlari.** `curl -I http://127.0.0.1:8000/static/pdfs/titul_1_1.pdf`
→ 404; Mini App va admin inspektor rasmni ko'rsatadi; boshqa ustoz
attempt fayli → 404; `npm run typecheck && npm run build` toza.

---

# FAZA 2 — Bot barqarorligi va kirish tozaligi

## T-11 · FSM handlerlariga `F.text` filtri va fallback

- **Zaiflik:** №11 · **Prioritet:** 🟠 · **Hajm:** S
- **Holat:** ✅ bajarildi 2026-09-16 (asl holat ❌) `groups.py:93-95`, `students.py:64-69`, `tests.py:112-114`,
  `tests.py:163-172` — `message.text.strip()` / `message.text.splitlines()`
  `F.text` siz. Rasm/stiker/voice → `AttributeError`, foydalanuvchiga javob
  yo'q, state tiqilib qoladi. Ustoz kalit kiritish holatida skan yuborsa ham
  shu (skan `scan.router` oxirida, FSM handler birinchi ushlaydi).

**Yechim.**
1. Har to'rt handlerga `F.text` qo'shing:
   `@router.message(GroupCreate.waiting_name, F.text)`.
2. Har state uchun fallback (yoki bitta umumiy — `start.py` ga, `StateFilter("*")`
   emas, aniq state'lar ro'yxati bilan) — routerlar tartibi `bot/main.py:45-50`:
   ```python
   @router.message(StateFilter(GroupCreate, StudentAdd, TestCreate), ~F.text)
   async def fsm_non_text(message, state):
       await message.answer("Iltimos matn yuboring yoki ❌ Bekor qilish tugmasini bosing.", reply_markup=cancel_inline_kb())
   ```
   Bu handler `groups.router` da (birinchi FSM routeri) turishi kerak, aks
   holda `scan.router` ushlaydi. Yoki: `scan.py` photo/document handlerlariga
   `StateFilter(None)` qo'shing — holatda turgan ustozga "avval amalni
   yakunlang yoki bekor qiling" deb ayting. **Ikkalasini ham qiling.**
3. `/start` va `/help` allaqachon `state.clear()` qiladi — o'zgarmaydi.

**Qabul mezonlari.** Guruh nomi kutilayotganda stiker → tushunarli xabar,
state saqlanadi, keyingi matn ishlaydi. Kalit kutilayotganda rasm →
ogohlantirish, skan navbatga qo'yilmaydi.

---

## T-12 · Telegram HTML injection — `escape()` hamma joyda

- **Zaiflik:** №16 · **Prioritet:** 🟠 · **Hajm:** S
- **Holat:** ✅ bajarildi 2026-09-16 (asl holat ❌) `services/telegram.py:escape()` mavjud, lekin faqat admin
  kodida import qilingan (`admin/users.py:54`) va u yerda ham `:502`
  (`Sabab: {body.reason}`) da **ishlatilmagan**.

**Foydalanuvchi matni escape'siz HTML'ga tushadigan joylar** (bot default
`parse_mode=HTML` — `main.py:29`):

| Fayl:qator | Matn |
|---|---|
| `start.py:63` | `first_name` |
| `groups.py:74`, `:114` | `group.name`, `name` |
| `students.py:39`, `:83`, `:86` | `s.full_name` (parse_mode berilmagan, lekin default HTML!) |
| `tests.py:124`, `:229`, `:304` | `title`, `test_title`, `test.title` |
| `results.py:137`, `:181`, `:282` | `group.name`, `test.title`, `student.full_name` |
| `services/grading.py:99-100`, `:153-154` | `test_title`, `student_name` |
| `worker/tasks.py:170` | caption `student.full_name — test.title` |
| `worker/tasks.py:399` va `_error_message` | `str(exc)` — istisno matni (ichida `<` bo'lishi mumkin) |
| `admin/users.py:502` | `body.reason` |
| `middlewares/access.py:84` | `blocked_reason` |
| `scan.py:75`, `:147`, `:194`, `:253` | `reason`/`exc` — plan nomi (`«{plan_name}»`) admin kiritadi, baribir escape |

**Yechim.** Har joyda `escape(...)`. `grading.py` va `tasks.py` `app.services.telegram`
ni import qila oladi (aiogram bog'liqligi bor — worker image'da ham
o'rnatilgan). Istisno matnini foydalanuvchiga umuman ko'rsatmang (T-19).

**Testlar.** `test_grade.py` ga `format_result_message(..., test_title="<b>x</b>")`
→ natijada `&lt;b&gt;`. Qo'lda: `<b>Test` nomli guruh yarating → xabar keladi.

---

## T-13 · Excel/CSV formula injection va fayl nomi sanitizatsiyasi

- **Zaiflik:** №17 · **Prioritet:** 🟠 · **Hajm:** S
- **Holat:** ✅ bajarildi 2026-09-16 (asl holat ❌) `services/excel.py:136-146`, `:187-196`, `:235-243`,
  `:281-289`; `services/history.py:168-177`. Fayl nomlari
  `results.py:358`, `:377`, `:396`.

**Yechim.**
1. `services/excel.py` ga:
   ```python
   _FORMULA_PREFIX = ("=", "+", "-", "@", "\t", "\r")
   def safe_cell(v):
       """Excel/LibreOffice formulani ishga tushirmasligi uchun xavfli prefiksni neytrallaydi."""
       if isinstance(v, str) and v.startswith(_FORMULA_PREFIX):
           return "'" + v
       return v
   ```
   `ws.append([...])` dagi har matn ustunini `safe_cell(r[i])` bilan o'rang.
   `history.py:results_to_csv` ham (`csv` modulida ham shu prefiks).
   Eslatma: `-` bilan boshlangan ism kam uchraydi, lekin `'-Ali` ko'rinishi
   qabul qilinadi.
2. `services/excel.py` ga `safe_filename(name: str, fallback="fayl") -> str`:
   `re.sub(r"[^\w\-]+", "_", name, flags=re.UNICODE)[:60] or fallback`.
   `results.py:358,377,396` shu bilan; `natijalar_o'quvchi_` dagi apostrof
   ham olib tashlansin.
3. Test: `app/tests/test_excel.py` — `export_*` DB talab qiladi; `safe_cell`
   va `safe_filename` uchun sof unit-test yozing.

---

## T-14 · O'lik/tugallanmagan UI elementlari

- **Zaiflik:** №25 · **Prioritet:** 🟡 · **Hajm:** S
- **Holat:** ✅ bajarildi 2026-09-16 (asl holat ❌)

**Yechim.**
1. `inline.py:152` `results:{test_id}` tugmasi — handler yo'q, tugma
   "aylanadi". `results.py:166` `show_res_test` dekoratoriga
   `@router.callback_query(F.data.startswith("results:"))` qo'shing (ikkala
   prefiks bitta handler). `res_test_menu_kb` "Orqaga" tugmasi
   `res_group_tests:` ga olib boradi — test menyusidan kelganda
   `test:{id}` ga qaytish mantiqiyroq; hozircha qabul qilinadi.
2. `results.py:51-82` `F.text == "📊 Natijalar"` — reply-keyboard yo'q
   (`reply.py` hech qayerda import qilinmaydi: `grep -rn "keyboards.reply" app` bo'sh).
   Handlerni va `app/bot/keyboards/reply.py` ni o'chiring.
3. `services/students.py:61 link_telegram` chaqirilmaydi → dashboard'da
   `telegram_id` doim `null` ("Ulanmagan"). Ikki yo'l: (a) `web_api.py:137,276`
   va `dashboard.html` dan `telegram_id` ko'rsatishni olib tashlash;
   (b) o'quvchi botga `/start <titul_uuid>` deep-link bilan kirib ulanish
   oqimi. **(a) ni qiling**, (b) — alohida feature, `docs/05` da "reja" deb
   belgilang (T-36).

---

## T-15 · Foydalanuvchi ismini yangilash va `db_user` ni handlerlarga uzatish

- **Zaiflik:** №26 · **Prioritet:** 🟡 · **Hajm:** S · **Bog'liqlik:** T-08 bilan birga qulay
- **Holat:** ✅ bajarildi 2026-09-16 (asl holat ❌) `services/groups.py:16-31` mavjud user'ni yangilamaydi;
  callback'dan `get_or_create_user(db, telegram_id)` (`groups.py:33`,
  `tests.py:41`, `results.py:46`) `full_name=None` bilan yaratadi.
  `AccessMiddleware` `data["db_user"]` beradi, lekin hech bir handler
  ishlatmaydi (`grep -rn db_user app/bot` faqat middleware).

**Yechim.**
1. `get_or_create_user`: mavjud bo'lsa va `full_name`/`username` berilgan
   bo'lib farq qilsa — yangilang (`db.flush()`).
2. `AccessMiddleware.__call__`: `user is None` bo'lsa ham
   `get_or_create_user(db, tg_user.id, tg_user.full_name, tg_user.username)`
   bilan yaratsin (shunda `/start` bosmagan callback'lar ham `full_name` li
   bo'ladi) va `last_seen_at` yangilanganda ism/username ham sinxronlansin.
   Yaratish middleware'da bo'lsa `scan.py` dagi "ro'yxatsiz" holati (T-09)
   faqat `is_blocked` ga qoladi — bu qabul qilinadi (ro'yxat = /start emas,
   balki birinchi xabar). **Agar** ro'yxat majburan `/start` orqali bo'lishi
   kerak bo'lsa — middleware yaratmasin, T-09 dagi rad qoladi. Tavsiya:
   middleware yaratsin, T-09 da `db_user` doim bor deb hisoblang.
3. Handlerlar `_get_user_id`/`_owner_id` o'rniga `db_user: User` parametrini
   qabul qilsin (aiogram `data` dan avtomatik inject). Uch helperni o'chiring.
4. `/start` da `ensure_subscription(db, user.id)` chaqiring (T-17).

---

## T-16 · `parse_key` takror raqamlarni rad etsin

- **Zaiflik:** №27 · **Prioritet:** 🟡 · **Hajm:** XS
- **Holat:** ✅ bajarildi 2026-09-16 (asl holat ❌) `services/tests.py:57-65` — `result[str(num)] = letter`
  ustidan yozadi; `"1-A 1-B 2-C"` 2 savolli test uchun `{"1":"B","2":"C"}`.

**Yechim.** Sikl ichida:
```python
if str(num) in result:
    raise ValueError(f"{num}-savol ikki marta kiritilgan.")
```
Test: `test_key_parse.py` ga `pytest.raises(ValueError, match="ikki marta")`.

---

## T-17 · Guruh/o'quvchi limitlari botda, yangi ustozga obuna

- **Zaiflik:** №10 (qoldiq) · **Prioritet:** 🟠 · **Hajm:** S
- **Holat:** ✅ bajarildi 2026-09-16 (asl holat ❌) `check_group_limit`/`check_student_limit` hech qayerda
  chaqirilmaydi (`grep` faqat `admin/subscriptions.py:354` `ensure_subscription`).

**Yechim.**
1. `groups.py:receive_group_name` — `create_group` dan oldin
   `allowed, reason = await check_group_limit(db, user_id)`; `not allowed and settings.enforce_quota`
   → `escape(reason)` bilan xabar, state tozalanadi.
2. `students.py:receive_student_names` — `add_students` dan oldin
   `check_student_limit(db, user_id, group_id, adding=len(names))`.
3. `start.py:cmd_start` — `ensure_subscription(db, user.id)` (admin panelda
   yangi ustoz darhol FREE tarif bilan ko'rinadi). `get_default_plan`
   `RuntimeError` bersa (003 seed yo'q) — log + davom (foydalanuvchini
   to'xtatmang).
4. `ENFORCE_QUOTA=false` da faqat `log.warning` (skan bilan bir xil siyosat).

---

# FAZA 3 — Worker va OMR

## T-18 · Worker resurslari: faylni bir marta yuklash, sahifa limiti, vaqt limiti, engine singleton

- **Zaiflik:** №14, №23 · **Prioritet:** 🟠 · **Hajm:** M
- **Holat:** ❌ `tasks.py:218` `read_qr_from_file` → `load_image` →
  `pdf_to_images` **barcha** sahifani rasterizatsiya qiladi; `:260` `run()`
  yana yuklaydi. `celery_app.py` da `task_time_limit` yo'q; `acks_late=True`
  → osilgan task ~1 soatdan keyin qayta yetkaziladi. `tasks.py:31-40` har
  taskda `create_engine`.

**Yechim.**
1. `omr/pipeline.py`:
   - `pdf_to_images(pdf_path, dpi, max_pages: int = 1)` — `for i, page in enumerate(doc)`, `i >= max_pages` → break; `doc.page_count > max_pages` bo'lsa `log.warning`.
   - `load_image(...)` → `max_pages` uzatadi; rasm uchun **dekoddan oldin**
     o'lchamni tekshiring: `PIL.Image.open(fp)` (lazy, faqat header) →
     `w*h > MAX_PIXELS (30_000_000)` → `ValueError("Rasm juda katta")`.
     PNG dekompressiya bombasi shu bilan yopiladi (`Image.MAX_IMAGE_PIXELS`
     ham o'rnating).
   - Yangi `run_on_image(gray, ...)`/`run` ga `images: list[np.ndarray] | None`
     parametri — tasks.py bir marta `load_image` qilib ikkala bosqichga
     bitta array beradi.
2. `tasks.py:omr_task`: `images = load_image(file_path, max_pages=1)`;
   `pre_uuid = read_qr(images[0])`; `run(images=images, ...)`. Ko'p sahifali
   PDF bo'lsa natija xabariga `"⚠️ Faqat 1-sahifa tekshirildi ({n} sahifa)"`
   qo'shing (№23 — har sahifani alohida attempt qilish alohida feature).
3. `celery_app.py`:
   ```python
   task_time_limit=300, task_soft_time_limit=240,
   task_ignore_result=True,            # T-23
   worker_max_tasks_per_child=200,     # OpenCV xotira sizishiga qarshi
   ```
   `SoftTimeLimitExceeded` ni `omr_task` da ushlab attempt → error, retry yo'q.
4. Engine: modul darajasida `_sync_engine = None` + `_get_sync_session()`
   `lru`-uslubda bir marta yaratsin (`broadcast_tasks.py` ham shundan
   foydalansin). `pool_pre_ping=True` qoladi.

**Qabul mezonlari.** 50 sahifali PDF → 1 sahifa, ogohlantirish; 20 000×20 000
PNG → "Rasm juda katta" xatosi, worker tirik; `celery inspect conf` da limitlar.

---

## T-19 · `omr_task` xato oqimi: doimiy/vaqtinchalik xatolarni ajratish

- **Zaiflik:** №15 · **Prioritet:** 🟠 · **Hajm:** S
- **Holat:** 🟡 `bubble_data`/`confidence` yoziladi (`tasks.py:346-354`).
  `:383-401` har istisnoda xabar yuborib keyin `self.retry` — 3 marta bir xil
  xabar; `ValueError` (buzuq fayl) ham retry.

**Yechim.**
```python
PERMANENT = (ValueError, FileNotFoundError, cv2.error, SoftTimeLimitExceeded)
except PERMANENT as exc:
    _mark_error(db, attempt_id, str(exc))
    _send_message_sync(chat_id, "❌ Varaqni o'qib bo'lmadi. Aniqroq suratga olib qayta yuboring.")
    return                          # retry YO'Q
except Exception as exc:            # DB/Redis/tarmoq
    db.rollback(); log.exception(...)
    if self.request.retries >= self.max_retries:
        _mark_error(...); _send_message_sync(chat_id, "❌ Vaqtinchalik xatolik. Birozdan keyin qayta yuboring.")
        return
    raise self.retry(exc=exc, countdown=60 * (self.request.retries + 1))
```
Istisno matni (`str(exc)`) foydalanuvchiga **yuborilmasin** (T-12). `pdf_task`
(`:173-176`) uchun ham xuddi shu (Titul topilmasa retry ma'nosiz).

---

## T-20 · 180° burilgan varaq va anchor sanity tekshiruvi

- **Zaiflik:** №13 · **Prioritet:** 🟠 · **Hajm:** M
- **Holat:** ❌ `omr/anchors.py:24-45` `order_points` rasm burchaklarini
  oladi; varaq teskari bo'lsa TL↔BR almashadi, grid oynadek buriladi, hamma
  javob "xato" — **indamay**. `:19-21` absolyut piksel maydon (`2000..50000`)
  12MP suratda noto'g'ri.

**Yechim.**
1. **Orientatsiya:** shablonda QR **yuqori-o'ng** burchakda
   (`pdf/templates/base.html:26` — `top: 9mm; right: 22mm`). `pyzbar.decode`
   `rect`/`polygon` beradi — `omr/qr.py:read_qr` `(uuid, center_xy)` qaytarsin
   (imzo o'zgaradi → `pipeline.py:159`, `:255`, `tasks.py` ni yangilang).
   `run_single` da anchorlar topilgach QR markazini anchor to'rtburchagiga
   nisbatan tekshiring: perspektiva matritsasi `M` bilan QR markazini warp
   fazosiga o'tkazing (`cv2.perspectiveTransform`); agar `x < W/2` va
   `y > H/2` (pastki-chap) bo'lsa → varaq 180° burilgan →
   `anchor_centers = np.roll(anchor_centers, 2, axis=0)` (TL↔BR, TR↔BL) va
   qayta warp. Boshqa kvadrantlar (90°) → `error="Varaq yon tomonga burilgan"`.
   QR o'qilmagan bo'lsa orientatsiyani aniqlab bo'lmaydi → `needs_review=True`
   + log.
2. **Maydon filtri nisbiy:** `img_area = gray.shape[0]*gray.shape[1]`;
   anchor 10mm A4'da ≈ `(10/210)^2 * img_area * ~0.9` → diapazon
   `[0.3, 3.0] * expected`. Konstantalarni `expected_area` dan hisoblang.
3. **To'rtburchak sanity:** 4 markaz `cv2.isContourConvex`, tomonlar
   nisbati `w/h ∈ [0.6, 0.8]` (A4 foydali maydon 184/271 ≈ 0.68),
   qarama-qarshi tomonlar farqi < 15%. O'tmasa keyingi 4 talikni sinang
   (kandidatlar 4 dan ko'p bo'lsa `itertools.combinations` maydon bo'yicha
   eng katta 8 tadan) yoki `None`.
4. `ASPECT_TOL_GLOBAL` (`:111`) funksiyadan keyin e'lon qilingan — ishlaydi,
   lekin chalkash; `ANCHOR_ASPECT_TOL` ni to'g'ridan-to'g'ri ishlating.
5. Test: `test_omr_regression.py` fixture'i bo'lsa `cv2.rotate(img, ROTATE_180)`
   bilan ham ishga tushirib bir xil `detected` kutish. Fixture yo'q bo'lsa
   `scripts/calibrate.py` bilan sintetik varaq (PDF → rasm) yarating va
   `app/tests/fixtures/` ga qo'ying (git'ga kichik JPG, <500KB).

---

## T-21 · 5 variantli test — layout'ga `E` qo'shish yoki tanlovdan olib tashlash

- **Zaiflik:** №12 · **Prioritet:** 🟠 · **Hajm:** A: XS / B: L
- **Holat:** ❌ `omr/layout.py:30,37,44` `options: ["A","B","C","D"]`;
  `inline.py:100` `vcount:5`; `tests.py:148,168` `"ABCDE"[:vcount]`.
- ⚠️ **FOYDALANUVCHI QARORI KERAK** (CLAUDE.md: bu alohida, kattaroq ish).

**Variant A (darhol, xavfsiz):** `inline.py:95-103` dan `5 (A-E)` tugmasini
olib tashlang; `receive_vcount` da `vcount not in (4,)` → rad. Bazadagi
mavjud `variant_count=5` testlar uchun `test_selected` da ogohlantirish
("5 variantli testlar hozircha qo'llanmaydi"). `services/tests.py:19 VALID_OPTIONS`
ni `"ABCD"` qiling (parse_key `E` ni rad etadi).

**Variant B (to'liq):** `LAYOUTS_MM` har blokga `"E"` qo'shing — joy
hisobi: 40/50: `x0=35, dx=9` → E markazi `35+4*9+3=74mm`, B blok `110` da —
sig'adi; `x0=110` → `149mm` — sig'adi. 90: `x0=155, dx=8` → E `155+32+2.5=189.5mm`,
foydali maydon `197mm` gacha — **tor**, `dx=7.5` qilib qayta kalibrlash kerak
(`scripts/calibrate.py`, `docs/03`). PDF shablonlari (`titul_*.html`)
`bubbles` ro'yxatidan chizadi — kod o'zgarmaydi, lekin sarlavha harflari
(`A B C D` matni) bo'lsa tekshiring. `test_layout.py:24` `expected = qcount * 4`
→ `vcount` parametrli. Eski chop etilgan titullar 4 doirali — `Test.variant_count`
bo'yicha grid tanlanadi, muammo yo'q.

**Tavsiya:** A hozir, B alohida sprint.

---

## T-22 · `fill_ratio` — to'liq kadr niqobi o'rniga ROI

- **Zaiflik:** №33 · **Prioritet:** 🟡 · **Hajm:** XS
- **Holat:** ❌ `omr/bubbles.py:39-41` har doira uchun `np.zeros_like(warped_bin)`
  (1449×2134) — 360 doira × 3MB.

**Yechim.**
```python
r_in = max(1, int(r * 0.8)); x0, y0 = max(0, cx - r_in), max(0, cy - r_in)
roi = warped_bin[y0:cy + r_in + 1, x0:cx + r_in + 1]
mask = np.zeros(roi.shape, np.uint8); cv2.circle(mask, (cx - x0, cy - y0), r_in, 255, -1)
```
Natija o'zgarmasligini `test_omr_regression` (fixture bo'lsa) yoki sintetik
`np` massivda eski/yangi funksiya solishtiruvi bilan tasdiqlang.

---

## T-23 · Celery natijalarini saqlamaslik

- **Zaiflik:** №32 · **Prioritet:** 🟡 · **Hajm:** XS
- **Holat:** ❌ `celery_app.py:15` `backend=redis`, `:30` `result_expires=86400`.
  `grep -rn "AsyncResult\|\.get(timeout" app` — natija hech qayerda o'qilmaydi
  (`task.id` faqat log'ga: `scan.py:116`, `attempts.py:75`).

**Yechim.** `task_ignore_result=True`; `backend` ni olib tashlang (Flower
`task_track_started` uchun broker events yetarli). `ScanResponse.task_id`
qoladi (informativ).

---

## T-24 · Titullarni yuborishda Telegram flood va ZIP

- **Zaiflik:** №22 · **Prioritet:** 🟠 · **Hajm:** M
- **Holat:** ❌ `tests.py:278-280` har titul uchun `pdf_task.delay(tid, chat_id)`
  → worker har PDF'ni alohida `send_document` (`tasks.py:165-171`) — 150
  o'quvchi = 150 xabar, `RetryAfter` faqat log (`:90-91`) → ba'zilari yetib
  bormaydi. `tests.py:377-388` ZIP xotirada, 50MB dan oshsa Telegram rad etadi.

**Yechim.**
1. Yangi task `tituls_batch_task(test_id, chat_id)`: barcha titullar uchun
   PDF render (mavjud `pdf_path` bo'lsa o'tkazib yuboradi), keyin **bitta**
   ZIP `settings.pdf_output_dir / f"tituls_{test.id}_{uuid4().hex}.zip"` ga
   diskda (`zipfile` streaming), hajmi > 45MB bo'lsa qismlarga bo'lib
   (`_part1.zip`, ...) yuboradi, oxirida ZIP faylni o'chiradi.
   `gen_tituls_all` (`tests.py:277-280`) shu taskni chaqiradi; `pdf_task`
   `notify_chat_id` siz qoladi (yakka regeneratsiya uchun).
2. `_send_message_sync`/`_send_document_sync` (`tasks.py:43-95`):
   `TelegramRetryAfter` → `await asyncio.sleep(exc.retry_after + 1)` va bir
   marta qayta urinish; `TelegramForbiddenError` → log, qayta urinmang.
3. `send_tituls_single` (`tests.py:338`) — har hujjat orasida
   `await asyncio.sleep(0.05)` va `TelegramRetryAfter` ushlash; 20 tadan
   ko'p bo'lsa ZIP tavsiya qiling.
4. `send_tituls_zip` (`:364`) — xotira o'rniga `tempfile.NamedTemporaryFile`
   + `FSInputFile`; 45MB dan oshsa qismlarga.

---

## T-25 · Skan qabul qilish nozikliklari

- **Zaiflik:** №30 · **Prioritet:** 🟡 · **Hajm:** S
- **Holat:** ❌ `scan.py:42` fayl nomi `{file_id}{suffix}` — bir xil rasm
  qayta yuborilsa worker o'qiyotgan fayl ustidan yoziladi; `:32-36`
  `image/heic`/`heif` qabul qilinadi, OpenCV o'qiy olmaydi; vaqtinchalik
  fayllar tozalanmaydi (`temp_uploads` volume o'sadi), lekin review
  (`source_file`) ularga bog'liq.

**Yechim.**
1. `_download_file`: `out = dest_dir / f"{uuid4().hex}{suffix}"`.
2. HEIC: **qaror** — (a) `ALLOWED_MIME` dan olib tashlash + "iPhone'da
   'Most Compatible' formatini yoqing yoki rasm sifatida (photo) yuboring"
   xabari; (b) `pillow-heif` qo'shib `load_image` da konvertatsiya. (a)
   sodda; foydalanuvchi bilan kelishing.
3. Fayl hayot sikli: skan `done`/`error` bo'lgach `source_file` ni
   `settings.uploads_dir` (yangi, doimiy volume `/data/uploads`) ga
   ko'chiring (`tasks.py` oxirida `shutil.move`, `attempt.source_file`
   yangilanadi). `temp_dir` da qolganlar (yetim) — `celery beat` kunlik task
   `cleanup_temp_files` 24 soatdan eski fayllarni o'chiradi. `uploads_dir`
   uchun retensiya (masalan 90 kun, `attempts` bilan birga) — admin
   sozlamasi, keyinroq.
4. Albom kollektori xotirada (`:27-28`) — restart'da yo'qoladi; qabul
   qilinadigan xavf, izohga yozing. Muqobil: Redis `LPUSH` + `EXPIRE`.

---

# FAZA 4 — API va admin

## T-26 · `/attempts/scan` ni tuzatish

- **Zaiflik:** №9 · **Prioritet:** 🟠 · **Hajm:** S
- **Holat:** ❌ `api/routes/attempts.py:62` `titul_id=1`; `:57`
  `scan_{id(content)}`; `:47` butun fayl RAM'da; `schemas/attempts.py:12`
  `titul_id: int` → pending attempt uchun `GET /attempts/{id}` 500.

**Yechim.**
1. `titul_id=None` (002 dan beri nullable).
2. Fayl: `settings.temp_dir / f"{uuid4().hex}{suffix}"`; oqimli yozish:
   ```python
   size = 0
   with tmp_path.open("wb") as f:
       while chunk := await file.read(1 << 20):
           size += len(chunk)
           if size > max_bytes: f.close(); tmp_path.unlink(missing_ok=True); raise HTTPException(413)
           f.write(chunk)
   ```
3. `AttemptOut.titul_id: Optional[int]`; `confidence`, `manual_override`
   ham qo'shing.
4. `chat_id: int = 0` — natija hech kimga bormaydi; endpoint ichki
   (`verify_internal_key`), `chat_id` majburiy `Query(..., gt=0)` qiling
   yoki natija yuborilmasligini docstring'da aniq yozing. T-09 egalik
   tekshiruvi worker'da — `chat_id` ga tegishli ustoz bo'lmasa error.
5. `docs/06_API.md` ni moslang (T-36).

---

## T-27 · Qo'lda tuzatishni izchil qilish (`web_api` review, `PATCH /attempts`)

- **Zaiflik:** №24 · **Prioritet:** 🟡 · **Hajm:** S · **Bog'liqlik:** T-07
- **Holat:** 🟡 `admin/scans.py:369-460 override_answers` — namuna
  (validatsiya, `manual_override`, `reviewed_by_id`, `reviewed_at`, audit).
  `web_api.py:354-399 review_attempt` — validatsiya yo'q, maydonlar
  to'ldirilmaydi. `attempts.py:101-106` `score` ni `percent`/`detail` siz
  yangilaydi.

**Yechim.**
1. `review_attempt`: `admin/scans.py:393-407` dagi harf/savol validatsiyasini
   umumiy funksiyaga chiqaring (`services/grading.py:validate_answers(answers, test)`)
   va ikkala joyda ishlating. `attempt.manual_override=True`,
   `reviewed_by_id=user.id`, `reviewed_at=now(utc)`. `corrected_answers`
   to'liq to'plam emas, faqat o'zgarganlar bo'lishi mumkin — admin'dagidek
   `merged = dict(attempt.detected); merged.update(...)`.
2. `AttemptPatch` dan `score` ni olib tashlang; `detected: Optional[dict]`
   qo'shib `grade()` bilan qayta hisoblang (test `attempt.titul.test` orqali,
   `selectinload`). `detail` ni to'g'ridan-to'g'ri yozishga ruxsat bermang.
3. `test_web_api.py` dagi review testi `manual_override is True` ni tekshirsin.

---

## T-28 · `initData` eskirish muddati

- **Zaiflik:** №20 · **Prioritet:** 🟠 · **Hajm:** XS
- **Holat:** ❌ `api/routes/auth.py:36` `_INIT_DATA_MAX_AGE = 0`.

**Yechim.** `config.py` ga `init_data_max_age_seconds: int = 86400` (Mini
App) va `admin_init_data_max_age_seconds: int = 300` (`/api/admin/auth/telegram`
uzoq muddatli refresh token beradi — qattiqroq). `validate_init_data(init_data, max_age)`
parametr qabul qilsin; `get_webapp_user` va `admin/auth.py:280` mos qiymat
bilan chaqiradi. `auth_date` yo'q bo'lsa — rad. Mini App 24 soatdan uzoq
ochiq qolsa 401 → frontend `Telegram.WebApp.close()`/qayta ochish xabari
(`dashboard.html` da 401 ushlash bor-yo'qligini tekshiring).

---

## T-29 · `/docs`, `/redoc` ni prod'da yopish

- **Zaiflik:** №21 (qoldiq) · **Prioritet:** 🟡 · **Hajm:** XS
- **Holat:** 🟡 CORS tuzatilgan. `main.py:36-37` docs ochiq.

**Yechim.** `config.py`: `enable_api_docs: bool = False`; `FastAPI(docs_url="/docs" if settings.enable_api_docs else None, redoc_url=..., openapi_url=...)`.
`.env.example` da `ENABLE_API_DOCS=false` izoh bilan. `docs/08` dev bo'limida
`true` qilish eslatmasi.

---

## T-30 · Admin auth: IP rate limit, ishonchli proxy, refresh rotatsiyasi, logout

- **Zaiflik:** №19 (qoldiq) · **Prioritet:** 🟠 · **Hajm:** M · **Bog'liqlik:** T-04 (proxy headers)
- **Holat:** 🟡 enumeratsiya tuzatilgan (`admin/auth.py:160-172`). Qolgan:
  IP bo'yicha limit yo'q; `services/audit.py:33-40` `X-Forwarded-For` ga
  ko'r ishonadi; `:308-341` refresh eski tokenni bekor qilmaydi; logout yo'q.

**Yechim.**
1. **IP limit** (Redis, `admin/auth.py`): `otp/request` 10/soat/IP,
   `otp/verify` 20/10 daqiqa/IP, `telegram` 30/10 daqiqa/IP. Helper
   `_rate_limit(redis, key, limit, window)` → `INCR` + `EXPIRE`, oshsa 429.
2. **IP manbai:** `X-Forwarded-For` ga ishonmang — uvicorn
   `--proxy-headers --forwarded-allow-ips=<TRUSTED_PROXY_IPS>` (T-04) bilan
   `request.client.host` allaqachon to'g'ri; `client_ip()` ni
   `request.client.host` ga qisqartiring. `.env.example`: `TRUSTED_PROXY_IPS=127.0.0.1`.
3. **Refresh rotatsiyasi:** `refresh` endpointida eski `payload.jti` ni
   Redis `admin:revoked:{jti}` ga `exp` gacha TTL bilan yozing; `decode_token`
   dan keyin `get_current_admin` va `refresh` da revoked tekshiruvi. Bir
   oilaga (`family_id` claim) tegishli refresh qayta ishlatilsa — butun oila
   bekor (token o'g'irlanganini bildiradi).
4. **Logout:** `POST /api/admin/auth/logout {refresh_token}` — access `jti`
   (header'dan) va refresh `jti` revoked; audit `ADMIN_LOGOUT` (enum'ga
   qo'shing). Frontend `client.ts` da logout chaqiruvi.
5. Testlar `test_admin_security.py` ga: refresh ikki marta → ikkinchisi 401;
   logout'dan keyin access 401.

---

## T-31 · `ilike` da `%`/`_` escape

- **Zaiflik:** №35 (qoldiq) · **Prioritet:** 🟡 · **Hajm:** XS
- **Holat:** ❌ 6 joy: `admin/users.py:120-121`, `admin/subscriptions.py:225`,
  `admin/explorer.py:88`, `:286`, `:364`.

**Yechim.** `app/api/admin/deps.py` (yoki `services/search.py`) ga:
```python
def like_pattern(term: str) -> str:
    """LIKE uchun foydalanuvchi matnini ekranlaydi (%, _, \\)."""
    t = term.strip().replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return f"%{t}%"
```
va `.ilike(like_pattern(search), escape="\\")`. Test: `"100%"` qidiruvi
faqat literal `100%` ni topadi.

---

## T-32 · "Bugun" O'zbekiston vaqti bo'yicha

- **Zaiflik:** №28 · **Prioritet:** 🟡 · **Hajm:** XS
- **Holat:** 🟡 naive tuzatilgan; `web_api.py:58-60` va
  `services/admin_metrics.py:60` UTC kun boshini oladi (Toshkent 05:00 gacha
  "kecha"ga tushadi).

**Yechim.** `config.py`: `app_timezone: str = "Asia/Tashkent"`; `core/time.py`:
```python
def local_day_start(now: datetime | None = None) -> datetime:
    tz = ZoneInfo(get_settings().app_timezone)
    local = (now or datetime.now(timezone.utc)).astimezone(tz)
    return local.replace(hour=0, minute=0, second=0, microsecond=0).astimezone(timezone.utc)
```
Ikkala joyda shu. `celery_app.py:24` `timezone` ham `settings.app_timezone`.
Excel'dagi `created_at` ham lokal vaqtga o'tkazilib `tzinfo=None` (CLAUDE.md
tuzoq 2) qilinsin.

---

## T-33 · `get_db` faqat o'zgarish bo'lsa commit qilsin

- **Zaiflik:** №29 · **Prioritet:** 🟢 · **Hajm:** XS
- **Holat:** ❌ `core/db.py:57-66`.

**Yechim.** `if session.new or session.dirty or session.deleted: await session.commit()`.
Diqqat: `attempts.py:patch_attempt` (`:108`) va `scan_file` (`:68`) faqat
`flush` qiladi va avto-commitga tayanadi — ular `dirty`/`new` bo'lgani uchun
baribir commit bo'ladi. Aniqlik uchun o'sha ikki joyga `await db.commit()`
qo'shing.

---

## T-34 · Loki handler: chegaralangan navbat

- **Zaiflik:** №31 · **Prioritet:** 🟡 · **Hajm:** XS
- **Holat:** ❌ `core/logging.py:14` `queue.Queue()` chegarasiz; `:54-57`
  Loki yotsa har yozuv 2s+1s.

**Yechim.** `queue.Queue(maxsize=2000)`; `emit` da `put_nowait`, `queue.Full`
→ yozuvni tashlab yuboring (va 60 soniyada bir marta stderr'ga "Loki navbati
to'lgan"). `_worker` da 50 tagacha yozuvni bitta so'rovga yig'ing
(`streams[0].values` ro'yxati), xato bo'lsa eksponensial kutish (1→30s).

---

# FAZA 5 — Sifat va hujjat

## T-35 · Testlarni izolyatsiya qilish

- **Zaiflik:** №34 · **Prioritet:** 🟠 · **Hajm:** M
- **Holat:** ❌ `test_web_api.py:24-31,150-167` `get_session_factory()`
  bilan `.env` dagi bazaga yozadi/o'chiradi (prod `.env` bilan ishga tushsa
  ma'lumot buziladi). Boshqa testlar DB'siz.

**Yechim.**
1. `conftest.py`:
   - Sessiya boshida `TEST_DATABASE_URL` env talab; yo'q bo'lsa DB testlarini
     `pytest.skip`. Qo'shimcha himoya: URL ichida `test` so'zi bo'lmasa
     `pytest.exit("TEST_DATABASE_URL 'test' so'zini o'z ichiga olishi shart")`.
   - `get_settings.cache_clear()` + `monkeypatch.setenv("DATABASE_URL", TEST_DATABASE_URL)`
     **importlardan oldin** (`app.core.db._engine` modul darajasida lazy —
     `_engine=None` ga qaytaring).
   - `alembic upgrade head` bir marta (subprocess yoki `alembic.command`),
     keyin har test `async with engine.connect() as conn: trans = await conn.begin(); session = AsyncSession(bind=conn, join_transaction_mode="create_savepoint")` → test oxirida `rollback`.
   - `app.dependency_overrides[get_db]` shu sessiyani beradi.
2. `docker-compose.yml` ga `postgres` da ikkinchi baza yaratish
   (`POSTGRES_MULTIPLE_DATABASES` skripti yoki `docs/08` da
   `CREATE DATABASE omrdb_test` buyrug'i). `CLAUDE.md` buyruqlar bo'limiga
   `TEST_DATABASE_URL=... pytest`.
3. T-06/T-07/T-08 testlari shu fixture'ga o'tkaziladi.

---

## T-36 · Hujjat/kod nomuvofiqligi

- **Zaiflik:** №36 · **Prioritet:** 🟢 · **Hajm:** S

**Yechim.** `docs/06_API.md` ni haqiqiy route'lar bilan yangilang
(`grep -rn "@router\.\(get\|post\|patch\|delete\)" app/api` ro'yxatidan);
`docs/05_BOT_FLOWS.md` da o'quvchi oqimlarini "Rejalashtirilgan (kodda yo'q)"
bo'limiga; `.env.example` (T-01) — har o'zgaruvchi izohi; `README.md`
setup qadamlarini `docs/08` ga havola qiling. `CLAUDE.md` "Ma'lum
muammolar" bo'limini bajarilgan tasklardan keyin yangilang.

---

## T-37 · `attempts.submitted_by_id` (migratsiya 004)

- **Zaiflik:** №37 · **Prioritet:** 🟢 · **Hajm:** S · **Bog'liqlik:** T-09 dan keyin foydali

**Yechim.** `app/alembic/versions/004_attempts_submitted_by.py`:
`submitted_by_id BIGINT NULL REFERENCES users(id) ON DELETE SET NULL` +
indeks. `models/attempt.py` ga `mapped_column(BigInteger, ForeignKey(...), nullable=True)`
va relationship. `scan.py:_enqueue_scan` yaratishda `submitted_by_id=owner.id`;
`attempts.py:scan_file` da `chat_id` dan user. `owned_attempt` (T-06)
`titul_id NULL` bo'lsa `submitted_by_id == owner_id` ga qaraydi — pending
skanlar ham Mini App'da ko'rinadi. Admin skan ro'yxatiga "Kim yubordi" ustuni
(`schemas/admin/scans.py`, `admin-ui` types + jadval).

---

## T-38 · Past prioritetli tozalash

- **Zaiflik:** №37 · **Prioritet:** 🟢 · **Hajm:** S

1. `scratch/*.png|jpg` (real skanlar, F.I.Sh bo'lishi mumkin) — `git rm --cached scratch/*.png scratch/*.jpg`,
   `.gitignore` ga `scratch/*.png`, `scratch/*.jpg`. Tarixdan o'chirish T-01
   qarori bilan birga.
2. Backup: `docs/08` ga `pg_dump` cron namunasi
   (`docker compose exec -T postgres pg_dump -U omruser omrdb | gzip > backup_$(date +%F).sql.gz`)
   va `pdf_data`/`uploads` volume'lari uchun `tar`. Avtomatlashtirish —
   server bo'yicha foydalanuvchi qarori.
3. Metrik/alert: minimal — `/health` DB va Redis ping qilsin
   (`SELECT 1`, `redis.ping()`), 503 qaytarsin; Grafana'da Loki `level=ERROR`
   bo'yicha alert qoidasi (`grafana/provisioning/alerting/`).
4. Dockerfile multi-stage Python (builder + runtime, `gcc`/`python3-dev`
   runtime'da qolmasin) — T-04 bilan birga qilish mumkin.

---

## T-39 · Obuna davri "anchor day" (ixtiyoriy)

- **Zaiflik:** №18 (qoldiq) · **Prioritet:** 🟢 · **Hajm:** S
- **Holat:** 🟡 `subscriptions.py:86-102` izohda ongli murosa deb yozilgan:
  31-kunda boshlangan obuna bir marta 28/30 ga surilib keyin o'sha kundan
  davom etadi.

**Yechim (agar kerak bo'lsa).** `subscriptions.anchor_day SMALLINT` ustuni
(migratsiya 004 bilan birga), `_next_period_end(start, anchor_day)` —
`day = min(anchor_day, monthrange(...))`. `ensure_period` va `assign_plan`
uzatadi. `test_subscriptions.py` ga 31-yanvar → 28-fevral → 31-mart testi.

---

## 3. Foydalanuvchi qarori kerak bo'lgan bandlar

| Task | Savol |
|---|---|
| T-01 | Git tarixini qayta yozamizmi (`filter-repo`)? Barcha klonlar sinadi. |
| T-03 | Serverda reverse proxy (nginx/caddy) bormi? Bo'lmasa API portini yopib bo'lmaydi. |
| T-05 | Serverda `docker-compose` (v1) mi yoki `docker compose` (v2)? |
| T-15 | Ro'yxatdan o'tish faqat `/start` orqalimi, yoki birinchi xabarda avtomatik? |
| T-21 | 5 variant: hozircha o'chiramizmi (A) yoki layout'ga E qo'shib kalibrlaymizmi (B)? |
| T-25 | HEIC: rad etamizmi yoki `pillow-heif` bilan konvertatsiya? |
| T-24 | Titullar faqat ZIP bo'lib kelsinmi, yoki "alohida" varianti (sekin, limitli) qolsinmi? |

---

## 4. Yakuniy tekshiruv ro'yxati (hammasi bajarilgach)

```bash
# Sirlar
grep -rnE '[0-9]{8,}:[A-Za-z0-9_-]{35}' --exclude-dir=.git . ; echo "token: $?"   # 1 kutiladi
# Portlar
docker compose config | grep -E '"\s*[0-9]+:[0-9]+"' ; echo "ochiq port: $?"       # 1 kutiladi
# Static
curl -s -o /dev/null -w "%{http_code}\n" http://127.0.0.1:8000/static/pdfs/x.pdf    # 404
# Testlar
TEST_DATABASE_URL=... docker compose run --rm --no-deps api pytest app/tests -q
cd admin-ui && npm run typecheck && npm run build
# Tenant
# — ikki ustoz bilan qo'lda: guruh/test/natija/Excel/PDF faqat o'zinikini ko'radi
```

`weaknesses.md` — tuzatilgan bandlarni o'chirmang; ustiga `✅ (T-XX, <sana>)`
belgisi qo'ying, shunda audit tarixi saqlanadi. `CLAUDE.md` "Ma'lum muammolar"
bo'limini ham yangilang.
