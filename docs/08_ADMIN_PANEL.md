# 08 — Admin Panel (React) va SaaS qatlami

Bu hujjat `/admin` manzilidagi React admin panelini, uni quvvatlaydigan
`/api/admin/*` endpointlarini va SaaS (tarif/kvota) qatlamini tavsiflaydi.

---

## 1. Umumiy ko'rinish

```
                    ┌──────────────────────────┐
  Brauzer  ────────▶│  FastAPI (api konteyner) │
  /admin            │                          │
                    │  /admin        → React SPA (statik, image ichida)
                    │  /api/admin/*  → JWT bilan himoyalangan REST
                    │  /api/web/*    → Mini App (initData) — eski oqim
                    │  /static/*     → skan rasmlari (OMR inspektori)
                    └────────┬─────────────────┘
                             │
             ┌───────────────┼────────────────┐
             ▼               ▼                ▼
        PostgreSQL        Redis          Telegram Bot API
      (plans,           (OTP kodlari,     (OTP, bloklash xabari,
       subscriptions,    Celery navbat)    e'lonlar, tuzatish xabari)
       audit_logs,
       broadcasts)
```

Panel **alohida konteyner emas**: u Docker image ichida yig'iladi va
FastAPI tomonidan statik fayl sifatida beriladi. Shu sababli prod'da
qo'shimcha port, nginx yoki CORS sozlash kerak emas.

---

## 2. Ma'lumotlar bazasi o'zgarishlari (migratsiya `003`)

### Yangi jadvallar

| Jadval | Vazifasi |
|---|---|
| `plans` | Tarif va uning limitlari (`NULL` limit = cheksiz) |
| `subscriptions` | Ustozning tarifga obunasi + joriy davr sarfi |
| `audit_logs` | Admin amallari jurnali (faqat qo'shiladi) |
| `broadcasts` | Telegram e'loni (matn, auditoriya, holat) |
| `broadcast_recipients` | Har bir qabul qiluvchi uchun yuborish natijasi |

### Kengaytirilgan jadvallar

`users`: `admin_role`, `is_blocked`, `blocked_reason`, `blocked_at`,
`blocked_by_id`, `last_seen_at`

`attempts`: `confidence`, `bubble_data`, `manual_override`,
`reviewed_by_id`, `reviewed_at`

### Nega `users.plan_id` va `users.quota_used` YO'Q

Tarif va sarf **faqat** `subscriptions` da saqlanadi. `users` ga dublikat
ustun qo'shilsa, ikki joyni bir vaqtda yangilash kerak bo'lardi va ular
albatta bir kun kelib bir-biriga mos kelmay qolardi (skan qabul qilinganda
bittasi yangilanib, ikkinchisi eskirib qoladi). Joriy tarif har doim
shu so'rov bilan olinadi:

```sql
SELECT * FROM subscriptions
WHERE user_id = :id AND status IN ('active', 'trial');
```

`uq_subscriptions_active_user` (qisman unique indeks) bitta ustozda bir
vaqtda bittadan ortiq faol obuna bo'lishini bazaning o'zida taqiqlaydi.

### Kvota davri — "lazy rollover"

Alohida cron kerak emas. Har safar kvota o'qilganda
`services/subscriptions.ensure_period()` `period_end` o'tganini tekshiradi
va kerak bo'lsa davrni keyingi oyga suradi hamda `scans_used` ni nolga
tushiradi. Bir necha oy o'tib ketgan bo'lsa ham joriy oyga yetib boradi.

Bonus kreditlar (`bonus_credits`) davr aylanishida **kuymaydi** — ularni
admin qo'lda beradi va qo'lda oladi.

---

## 3. Autentifikatsiya

Parol yo'q. Admin o'zini Telegram orqali tasdiqlaydi:

**A) Kompyuter brauzeri (asosiy yo'l)**

```
POST /api/admin/auth/otp/request   {telegram_id}
   → bot 6 xonali kod yuboradi (Redis'da 5 daqiqa yashaydi)
POST /api/admin/auth/otp/verify    {telegram_id, code}
   → {access_token, refresh_token, profile}
```

**B) Telegram Mini App ichida**

```
POST /api/admin/auth/telegram      {init_data}
   → initData imzosi HMAC-SHA256 bilan tekshiriladi → shu tokenlar
```

### Birinchi admin (bootstrap)

`.env` dagi `ADMIN_TELEGRAM_IDS` ro'yxatidagi telegram_id birinchi marta
kirganda avtomatik `SUPERADMIN` qilib belgilanadi — bazaga qo'lda SQL
yozish shart emas. Migratsiya `003` esa eski `role='admin'` bo'lganlarni
`SUPERADMIN` ga o'tkazadi.

```bash
# .env
ADMIN_TELEGRAM_IDS=123456789,987654321
```

Foydalanuvchi avval botda `/start` bosgan bo'lishi kerak (aks holda
bazada qatori yo'q va kod yuborilmaydi).

### Xavfsizlik jihatlari

- **Rol tokendan emas, BAZADAN o'qiladi.** Eski token bilan yuqori rol
  da'vo qilib bo'lmaydi; rol olib qo'yilsa keyingi so'rovdayoq kuchga
  kiradi.
- OTP javobi har doim bir xil ("kod yuborildi") — telegram_id admin
  ekanini oshkor qilmaydi (user enumeration'dan himoya).
- 5 ta noto'g'ri urinishdan keyin kod bekor qilinadi.
- Bloklangan admin `403` oladi, token amal qilsa ham.

---

## 4. Rollar

| Rol | Huquqlar |
|---|---|
| `ANALYST` | Faqat o'qish (dashboard, jadvallar, audit, eksport) |
| `SUPPORT_OPERATOR` | + bloklash, natijani qo'lda tuzatish, e'lon yuborish |
| `SUPERADMIN` | + tarif yaratish/tahrirlash, obuna biriktirish, rol berish |

Iyerarxik: yuqoridagi pastdagining hamma huquqiga ega
(`app/api/admin/deps.py: admin_required`).

---

## 5. Endpointlar

| Metod | Yo'l | Minimal rol |
|---|---|---|
| POST | `/api/admin/auth/otp/request` | — |
| POST | `/api/admin/auth/otp/verify` | — |
| POST | `/api/admin/auth/telegram` | — |
| POST | `/api/admin/auth/refresh` | — |
| GET | `/api/admin/auth/me` | ANALYST |
| GET | `/api/admin/dashboard/overview` | ANALYST |
| GET | `/api/admin/dashboard/{kpi,scans-timeseries,teacher-activity,question-distribution,failures,plans-usage,top-teachers,system}` | ANALYST |
| GET | `/api/admin/users` · `/users/{id}` · `/users/export` | ANALYST |
| POST | `/api/admin/users/{id}/block` | SUPPORT_OPERATOR |
| PATCH | `/api/admin/users/{id}/role` | SUPERADMIN |
| GET | `/api/admin/groups` · `/groups/{id}` · `/groups/{id}/export` | ANALYST |
| GET | `/api/admin/students` · `/students/{id}` · `/students/{id}/export` | ANALYST |
| GET | `/api/admin/tests` · `/tests/{id}` · `/tests/{id}/export` | ANALYST |
| GET | `/api/admin/scans` · `/scans/review-queue` · `/scans/{id}` | ANALYST |
| GET | `/api/admin/scans/{id}/file/{source,debug}` — skan surati / OMR annotatsiyasi (fayl) | ANALYST |
| POST | `/api/admin/scans/{id}/override` · `/scans/{id}/resolve` | SUPPORT_OPERATOR |
| GET | `/api/admin/plans` · `/subscriptions` | ANALYST |
| POST, PUT | `/api/admin/plans` · `/plans/{id}` | SUPERADMIN |
| POST | `/api/admin/subscriptions/{user_id}/{assign,credits,cancel}` | SUPERADMIN |
| GET | `/api/admin/broadcasts` · `/broadcasts/{id}` | ANALYST |
| POST | `/api/admin/broadcasts` · `/{id}/send` · `/{id}/cancel` | SUPPORT_OPERATOR |
| POST | `/api/admin/broadcasts/preview` | ANALYST |
| GET | `/api/admin/audit-logs` · `/audit-logs/actions` | ANALYST |
| GET | `/api/admin/system/{status,failed-tasks,stuck-tasks}` | ANALYST |

To'liq sxema: `http://localhost:8000/docs`

---

## 6. "OMR aniqlik darajasi" nimani anglatadi

Bu **o'quvchilarning bali emas**. Bu tizim varaqni qanchalik ishonchli
o'qiganini bildiradi:

```
accuracy = (status='done' VA needs_review=false) / (jami skanlar)
```

Ya'ni xato bergan (`error`) yoki ikkilanib qo'lda ko'rikka tushgan
(`needs_review`) varaqlar "muvaffaqiyatsiz o'qish" hisoblanadi.
O'quvchilarning o'rtacha bali alohida ko'rsatkich: `avg_score_percent`.

---

## 7. Kvota (SaaS) qanday ishlaydi

`ENFORCE_QUOTA=false` (standart) — limitlar **hisoblanadi**, lekin skan
rad etilmaydi. Bu yumshoq ishga tushirish uchun: avval haqiqiy
foydalanish hajmini ko'rasiz, keyin limitlarni yoqasiz.

`ENFORCE_QUOTA=true` — limit tugagan ustoz varaq yubora olmaydi va
botda tushuntirish xabarini oladi.

Skan hisobi **navbatga qo'yilganda** olinadi (natijadan qat'i nazar) —
aks holda xato bergan varaqni cheksiz qayta yuborib limitni aylanib
o'tish mumkin bo'lardi.

Poyga holatidan himoya: `consume_scan()` obuna qatorini
`SELECT ... FOR UPDATE` bilan qulflaydi, shu sababli bir vaqtda kelgan
bir nechta skan limitdan oshib ketolmaydi.

---

## 8. Ishga tushirish

### 8.1. Prod (Docker)

```bash
cp .env.example .env
```

Tasodifiy kalitlar (`SECRET_KEY` va `INTERNAL_API_KEY` uchun alohida):

```bash
python -c "import secrets; print(secrets.token_hex(32))"
```

`.env` da `CHANGE_ME_...` bilan belgilangan hamma narsani to'ldiring —
ayniqsa `ADMIN_TELEGRAM_IDS`, `SECRET_KEY`, `INTERNAL_API_KEY`,
`POSTGRES_PASSWORD`, `REDIS_PASSWORD`, `GRAFANA_ADMIN_PASSWORD`. Keyin:

```bash
docker compose build
docker compose up -d postgres redis
docker compose run --rm api alembic upgrade head
docker compose up -d
```

**Tartib muhim:** migratsiya ilova konteynerlaridan OLDIN. Yangi kod
yangi ustunlarni SELECT qiladi — teskari tartibda bot ham, API ham
migratsiya tugaguncha yiqilib turadi. Shu sababli `.github/workflows/deploy.yml`
ham aynan shu ketma-ketlikda ishlaydi.

Panel: `http://127.0.0.1:8000/admin`
API hujjati: `http://127.0.0.1:8000/docs`

Portlar faqat `127.0.0.1` ga bog'langan (postgres 5433, redis 6380, api
8000, loki 3100, grafana 3001). Uzoq serverda SSH tunnel bilan oching:

```bash
ssh -L 8000:127.0.0.1:8000 -L 3001:127.0.0.1:3001 user@server
```

`docker compose build` `node:22-slim` bosqichida `npm run build` ni
bajaradi va faqat tayyor `dist` ni yakuniy image'ga ko'chiradi — Node
runtime prod image'ga tushmaydi.

Prod serverda `.env` ga `INSTALL_DEV=false` qo'shing — image'ga pytest va
boshqa test bog'liqliklari tushmaydi (lekin unda `pytest` buyrug'i ham
ishlamay qoladi).

### 8.1.1. Mavjud o'rnatmani yangilash (buzuvchi o'zgarishlar)

Redis paroli, majburiy `.env` o'zgaruvchilari va non-root konteyner
qo'shilgandan keyin **eski `.env` bilan compose ishga tushmaydi**. Qilish
kerak bo'lgan ishlar:

1. `.env` ga yangi qatorlarni qo'shing:

   ```
   REDIS_PASSWORD=<yangi parol>
   REDIS_URL=redis://:<yangi parol>@redis:6379/0
   GRAFANA_ADMIN_PASSWORD=<yangi parol>
   API_BIND_HOST=127.0.0.1
   TRUSTED_PROXY_IPS=127.0.0.1
   INSTALL_DEV=false
   ```

2. **`POSTGRES_PASSWORD` ni o'zgartirmoqchi bo'lsangiz** — `.env` ni
   tahrirlash YETARLI EMAS. Postgres parolni faqat baza birinchi marta
   yaratilganda o'rnatadi; mavjud volume'da eski parol qoladi va ilova
   autentifikatsiyadan o'tolmaydi. Avval bazada o'zgartiring:

   ```bash
   docker compose exec -T postgres psql -U omruser -d omrdb \
     -c "ALTER USER omruser PASSWORD '<yangi parol>';"
   ```

   Keyin `.env` dagi `POSTGRES_PASSWORD`, `DATABASE_URL` va
   `SYNC_DATABASE_URL` ni bir xil yangi parolga keltiring.
   Parolni o'zgartirmasangiz — eskisini shu uchta joyga yozib qo'ying,
   hech narsa buzilmaydi.

3. Redis paroli qo'shilgach eski navbat va FSM state'lar o'qilmay qoladi
   (parol server flag'i, ma'lumot yo'qolmaydi, lekin ulanish yangilanadi).
   Konteynerlarni qayta yarating: `docker compose up -d --force-recreate redis bot worker api`.

4. Volume egaligi: ilova endi `appuser` (uid 10001) nomidan ishlaydi.
   Eski named volume'lar `root` egaligida — `docker/entrypoint.sh` buni
   birinchi ishga tushishda **avtomatik** to'g'rilaydi (konteyner root
   bilan boshlanib, `chown` qilib, `gosu` bilan huquqni tushiradi).
   Qo'lda hech narsa qilish shart emas; birinchi start bir-necha soniya
   uzoqroq davom etishi mumkin.

### 8.2. Frontend dev rejimi (tezkor qayta yuklash bilan)

```bash
cd admin-ui && cp .env.example .env.local && npm install && npm run dev
```

Panel `http://localhost:5173` da ochiladi. Vite `/api` va `/static`
so'rovlarini `http://localhost:8000` ga proksi qiladi, shu sababli CORS
kerak emas. Backend boshqa manzilda bo'lsa `admin-ui/.env.local` da:

```
VITE_API_PROXY_TARGET=http://192.168.1.50:8000
```

Proksi ishlatmasdan to'g'ridan-to'g'ri murojaat qilmoqchi bo'lsangiz —
backend `.env` da CORS'ni oching:

```
ADMIN_CORS_ORIGINS=http://localhost:5173
```

### 8.3. Foydali buyruqlar

TypeScript tekshiruvi va prod build:

```bash
cd admin-ui && npm run typecheck && npm run build
```

Testlar:

```bash
docker compose run --rm --no-deps api pytest app/tests -q
```

Loglar:

```bash
docker compose logs -f api
```

---

## 9. Frontend tuzilishi

```
admin-ui/src/
├── api/
│   ├── client.ts      # axios + JWT interceptor (401 → refresh → qayta urinish)
│   ├── queries.ts     # TanStack Query hook'lari va kalitlar
│   └── types.ts       # backend javoblarining TS turlari
├── components/
│   ├── ui/            # shadcn/ui primitivlari (button, card, dialog, …)
│   ├── DataTable.tsx  # TanStack Table + server-side sahifalash
│   ├── KpiCard.tsx
│   └── StatusBadge.tsx
├── features/
│   ├── auth/          # LoginPage (OTP oqimi)
│   ├── dashboard/     # DashboardOverviewPage + charts.tsx
│   ├── teachers/      # jadval + drawer + bloklash/tarif modallari
│   ├── explorer/      # guruh / o'quvchi / test
│   ├── scans/         # ro'yxat + OMR inspektori + ko'rik navbati
│   ├── subscriptions/ # tariflar + obunalar
│   ├── broadcasts/    # e'lon yozish + Telegram ko'rinishi
│   ├── audit/
│   └── system/
├── hooks/             # useAuth, useDebounce
├── layouts/           # AdminLayout (sidebar, mavzu almashtirish)
└── lib/               # cn(), formatlash yordamchilari
```

### Grafik ranglari haqida

`src/index.css` da ikki xil to'plam bor va ular aralashtirilmaydi:

- `--series-1..3` — **kategorik** slotlar (identifikatsiya uchun), qat'iy
  tartibda ishlatiladi va hech qachon aylantirilmaydi.
- `--status-good / warning / critical` — **holat** ranglari. Ular oddiy
  "4-qator rangi" sifatida qayta ishlatilmaydi va har doim yozuv bilan
  birga keladi.

Ranglar ko'z bilan tanlanmagan — rang ko'rlik (CVD) ajratuvchanligi va
fon bilan kontrast bo'yicha tekshirilgan. Har bir grafikda legend va
tooltip bor, shunda rang yagona ma'no tashuvchi kanal bo'lib qolmaydi.
Ikki y-o'qli grafik yo'q.

---

## 10. Tez-tez uchraydigan muammolar

**Panelga kira olmayapman: 503 "SECRET_KEY namunaviy yoki juda qisqa"**
`.env` dagi `SECRET_KEY` hali `.env.example` dagi namunaviy qiymatda.
Bu kalit admin tokenlarini imzolaydi va u ochiq repoda turgani uchun uni
bilgan har kim o'ziga SUPERADMIN tokeni yasay olardi — shu sababli panel
ataylab ishlamaydi. Yangi kalit yarating:

```bash
python -c "import secrets; print(secrets.token_hex(32))"
```

Uni `.env` ga yozing va `docker compose up -d api` bilan qayta ishga
tushiring. Bot va Mini App bu kalitga bog'liq emas — ular ishlab turadi.

**`/admin` 404 qaytaradi**
`admin-ui/dist` yig'ilmagan. `docker compose build api` ni qayta ishga
tushiring (yoki lokal ishlatayotgan bo'lsangiz `cd admin-ui && npm run build`).

**"Telegram orqali kod yuborilmadi" (502)**
Foydalanuvchi botda hali `/start` bosmagan yoki botni bloklagan.
Shuningdek `BOT_TOKEN` to'g'ri ekanini tekshiring.

**"Admin panelga kirish huquqi yo'q" (403)**
`ADMIN_TELEGRAM_IDS` ga telegram_id qo'shing va `api` konteynerini qayta
ishga tushiring, yoki bazada qo'lda:

```sql
UPDATE users SET admin_role = 'SUPERADMIN' WHERE telegram_id = 123456789;
```

**Tizim holatida Celery "unknown"**
`worker` konteyneri ishlamayapti yoki Redis'ga ulanmagan:

```bash
docker compose ps worker && docker compose logs worker
```

**OMR inspektorida "Rasm saqlanmagan"**
Annotatsiya rasmi faqat `OMR_DEBUG=true` bo'lganda saqlanadi. Asl surat
`TEMP_DIR` da turadi va u vaqtinchalik volume — eski skanlar tozalangan
bo'lishi mumkin.

**Eski skanlarda "Ishonchlilik: —"**
`confidence` va `bubble_data` ustunlari `003` migratsiyasidan keyin paydo
bo'ldi. Undan oldingi skanlarda bu ma'lumot saqlanmagan; yangi skanlar
to'liq ko'rinadi.
