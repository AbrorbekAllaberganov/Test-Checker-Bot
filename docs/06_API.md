# 06 — API (FastAPI)

**Yangilangan:** 2026-09-19. Bu ro'yxat KODDAN olingan (`grep -rn "@router\."
app/api`) — ilgari hujjatdagi yo'llar kod bilan mos kelmasdi
(weaknesses.md №36).

Uch xil auth zonasi bor va ular bir-biriga bog'liq emas:

| Zona | Prefiks | Auth | Kim ishlatadi |
|---|---|---|---|
| Ichki | `/groups`, `/tests`, `/tituls`, `/results`, `/attempts` | `X-Internal-Key` sarlavhasi (`INTERNAL_API_KEY`) | bot, worker, skriptlar |
| Mini App | `/api/web/*`, `/api/auth/*` | Telegram `initData` HMAC imzosi (`Authorization: tma <initData>`) | ustozning dashboard'i |
| Admin panel | `/api/admin/*` | JWT Bearer (`/api/admin/auth/*` beradi) | React admin paneli |

**Muhim:**
- `INTERNAL_API_KEY` yoki `SECRET_KEY` namunaviy qiymatda qolsa tegishli
  zona **ataylab 503** qaytaradi (`core/security.py`).
- `initData` endi **eskiradi**: Mini App uchun `INIT_DATA_MAX_AGE_SECONDS`
  (24 soat), admin kirishi uchun `ADMIN_INIT_DATA_MAX_AGE_SECONDS` (5 daqiqa).
- `/docs`, `/redoc`, `/openapi.json` prod'da **yopiq** (`ENABLE_API_DOCS=false`).
- `/static/*` mount'lari **yo'q**; fayllar faqat egalik tekshiruvli
  endpointlar orqali beriladi.

---

## Servis holati

```
GET  /health              -> {"status":"ok","checks":{"database":"ok","redis":"ok"}}
GET  /health?deep=false   -> {"status":"ok"}   (faqat jarayon tirikligi)
```
`deep=true` (standart) DB va Redis'ni ham tekshiradi va nosozda **503** beradi.

```
GET  /login       -> HTML (bot orqali kirish sahifasi)
GET  /dashboard   -> HTML (Mini App)
GET  /admin[/...] -> React SPA (admin-ui/dist mavjud bo'lsa)
```

---

## 1. Ichki API (`X-Internal-Key`)

### Guruhlar — `/groups`
```
POST   /groups                      {name, owner_id}   -> GroupOut
GET    /groups                      ?owner_id=         -> [GroupOut]
GET    /groups/{group_id}
DELETE /groups/{group_id}
GET    /groups/{group_id}/students                     -> [StudentOut]
```

### Testlar — `/tests`
```
GET    /tests/groups/{group_id}                        -> [TestOut]
GET    /tests/{test_id}
PATCH  /tests/{test_id}             {title?, answer_key?}
```

### Titullar — `/tituls`
```
POST   /tituls/tests/{test_id}/generate                -> [titul_id]
GET    /tituls/tests/{test_id}                         -> [TitulOut]
GET    /tituls/{titul_uuid}/pdf                        -> PDF
```

### Natijalar — `/results`
```
GET    /results/tests/{test_id}
GET    /results/tests/{test_id}/export                 -> XLSX
GET    /results/students/{student_id}/history
```

### Skanlar — `/attempts`
```
POST   /attempts/scan?chat_id=<tg>   multipart: file   -> 202 {task_id}
GET    /attempts/{attempt_id}                          -> AttemptOut
PATCH  /attempts/{attempt_id}        {needs_review?, detected?}
```

`POST /attempts/scan`:
- `chat_id` **majburiy** (`>0`): natija shu chatga boradi va worker aynan shu
  chatdagi ustoz titul egasi ekanini tekshiradi.
- Fayl **oqimli** yoziladi; `MAX_IMAGE_MB` dan oshsa 413 (butun fayl RAM'ga
  o'qilmaydi).
- Pending attempt `titul_id = NULL` bilan yaratiladi (QR ni worker o'qiydi).

`PATCH /attempts/{id}`: `score`/`detail` ni to'g'ridan-to'g'ri yozib bo'lmaydi.
Faqat `detected` (o'zgargan savollar) yuboriladi va ball `grade()` bilan qayta
hisoblanadi; `manual_override=true` bo'ladi.

---

## 2. Mini App API (`initData` imzosi)

```
GET  /api/auth/me                                  -> {telegram_id, full_name, username}

GET  /api/web/dashboard-stats
GET  /api/web/groups
GET  /api/web/groups/{group_id}
GET  /api/web/tests/{test_id}
GET  /api/web/students/{student_id}
GET  /api/web/attempts/{attempt_id}
GET  /api/web/attempts/{attempt_id}/file/{kind}    kind = source | debug
POST /api/web/attempts/{attempt_id}/review         {corrected_answers: {"7":"B"}}
```

**Tenant izolyatsiyasi:** har endpoint faqat joriy ustozning ma'lumotini
qaytaradi. Begona obyekt → **404** (403 emas: mavjudligini oshkor qilmaymiz).
Zanjir `services/access.py` da.

`POST .../review`: `corrected_answers` to'liq to'plam bo'lishi shart emas —
faqat o'zgargan savollar mavjud `detected` ustiga qo'yiladi. Harf yoki savol
raqami noto'g'ri bo'lsa **422**.

---

## 3. Admin API (`/api/admin`, JWT Bearer)

### Auth — `/api/admin/auth`
```
POST /otp/request    {telegram_id}              -> bot 6 xonali kod yuboradi
POST /otp/verify     {telegram_id, code}        -> TokenPair
POST /telegram       {init_data}                -> TokenPair
POST /refresh        {refresh_token}            -> TokenPair (ROTATSIYA)
POST /logout         {refresh_token?}           -> tokenlar bekor qilinadi
GET  /me                                        -> AdminProfile
```
- Refresh **rotatsiya**: eski token darhol bekor qilinadi. Bekor qilingan
  refresh qayta kelsa — butun sessiya oilasi (`fam` claim) yopiladi.
- IP bo'yicha limit: `otp/request` 10/soat, `otp/verify` 20/10 daq,
  `telegram` 30/10 daq → oshsa **429**.

### Dashboard — `/api/admin/dashboard`
```
GET /kpi  /scans-timeseries  /teacher-activity  /question-distribution
GET /failures  /plans-usage  /top-teachers  /system  /overview
```

### Foydalanuvchilar — `/api/admin/users`
```
GET   /users            ?search=&blocked=&admin_only=&plan_code=
GET   /users/export                             -> XLSX
GET   /users/{user_id}
POST  /users/{user_id}/block     {blocked, reason}
PATCH /users/{user_id}/role      {admin_role}
```

### Explorer — `/api/admin`
```
GET /groups    /groups/{id}    /groups/{id}/export
GET /students  /students/{id}  /students/{id}/export
GET /tests     /tests/{id}     /tests/{id}/export
```

### Skanlar — `/api/admin/scans`
```
GET  /scans                  ?status=&needs_review=&owner_id=&test_id=&group_id=
                             &date_from=&date_to=&max_confidence=
GET  /scans/{attempt_id}                         -> OMR inspektori
GET  /scans/{attempt_id}/file/{kind}             kind = source | debug
POST /scans/{attempt_id}/override  {answers}     -> qo'lda tuzatish + audit
POST /scans/{attempt_id}/resolve
```

### Tarif va obuna — `/api/admin`
```
GET  /plans
POST /plans
PUT  /plans/{plan_id}
POST /subscriptions/{user_id}/assign   {plan_code, duration_days?}
POST /subscriptions/{user_id}/credits  {credits}
POST /subscriptions/{user_id}/cancel
```

### E'lonlar — `/api/admin/broadcasts`
```
GET  /broadcasts
POST /broadcasts/preview
POST /broadcasts
GET  /broadcasts/{id}
POST /broadcasts/{id}/send
POST /broadcasts/{id}/cancel
```

### Audit va tizim
```
GET /api/admin/audit-logs           ?actor_id=&action=&date_from=&date_to=
GET /api/admin/audit-logs/actions
GET /api/admin/system/status
GET /api/admin/system/failed-tasks
GET /api/admin/system/stuck-tasks
```

**RBAC:** `ANALYST` < `SUPPORT_OPERATOR` < `SUPERADMIN`. Rol **tokendan emas,
bazadan** o'qiladi (`api/admin/deps.py`) — rol olib qo'yilishi darhol kuchga
kiradi. Batafsil: `docs/08_ADMIN_PANEL.md`.

---

## Xato javoblari

| Kod | Ma'nosi |
|---|---|
| 401 | Auth yo'q/yaroqsiz; sessiya bekor qilingan |
| 403 | Kalit noto'g'ri yoki rol yetarli emas |
| 404 | Topilmadi **yoki begona obyekt** (ataylab farqlanmaydi) |
| 413 | Fayl juda katta (`MAX_IMAGE_MB`) |
| 415 | Fayl turi qo'llanmaydi |
| 422 | Validatsiya (noto'g'ri javob harfi, savol raqami) |
| 429 | Rate limit (OTP, login) |
| 503 | Server noto'g'ri sozlangan (namunaviy kalit) yoki DB/Redis yotgan |
