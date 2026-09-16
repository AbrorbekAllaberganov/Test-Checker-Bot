# Loyihani ishga tushirish va to'xtatish

Kundalik ish uchun qo'llanma. Hamma narsa Docker ichida ishlaydi — lokal
Python yoki Postgres o'rnatish shart emas.

> Windows'da avval **Docker Desktop** ishga tushgan bo'lishi kerak.
> Ishlayotganini tekshirish: `docker info`. Xato bersa Docker Desktop'ni
> oching va "Engine running" yozuvini kuting.

---

## Eng kerakli 4 ta buyruq

```bash
docker compose up -d          # ishga tushirish
docker compose stop           # to'xtatish (ma'lumot saqlanadi)
docker compose logs -f bot    # loglarni kuzatish
docker compose ps             # holatni ko'rish
```

---

## 1. Birinchi marta ishga tushirish

Faqat bir marta, yoki `.env` yo'qolgan bo'lsa.

```bash
cp .env.example .env
```

`.env` dagi barcha `CHANGE_ME_...` qiymatlarni to'ldiring. Majburiylari:
`BOT_TOKEN`, `POSTGRES_PASSWORD`, `REDIS_PASSWORD`, `REDIS_URL`,
`SECRET_KEY`, `INTERNAL_API_KEY`, `GRAFANA_ADMIN_PASSWORD`. Tasodifiy
kalit generatsiya qilish:

```bash
python -c "import secrets; print(secrets.token_hex(32))"
```

Keyin:

```bash
docker compose build                      # image'larni yig'ish (~5-10 daq)
docker compose up -d postgres redis       # avval baza va Redis
docker compose run --rm api alembic upgrade head   # jadvallarni yaratish
docker compose up -d                      # qolgan hamma servis
docker compose ps                         # hammasi "running" ekanini tekshiring
```

> **Tartib muhim.** Migratsiya `up -d` dan OLDIN. Yangi kod yangi
> ustunlarni o'qiydi — teskari tartibda bot va API migratsiya tugaguncha
> yiqilib turadi.

---

## 2. Kundalik ishga tushirish va to'xtatish

Kod o'zgarmagan bo'lsa:

```bash
docker compose up -d      # ishga tushirish
docker compose stop       # to'xtatish
```

`stop` konteynerlarni to'xtatadi, lekin o'chirmaydi. Baza, Redis navbati,
PDF'lar va skanlar joyida qoladi. Kompyuterni qayta yoqqanda ular
o'z-o'zidan ko'tarilmaydi — qaytadan `up -d` qilasiz.

Bitta servisni to'xtatish yoki qayta ishga tushirish:

```bash
docker compose stop bot
docker compose start bot
docker compose restart worker
```

### `stop` va `down` farqi

| Buyruq | Konteynerlar | Ma'lumot (baza, PDF) |
|---|---|---|
| `docker compose stop` | to'xtaydi, saqlanadi | saqlanadi |
| `docker compose down` | o'chiriladi | **saqlanadi** |
| `docker compose down -v` | o'chiriladi | **YO'Q QILINADI** |

`down` dan keyin `up -d` konteynerlarni qaytadan yaratadi — bu normal.
`-v` esa baza volumelarini ham o'chiradi: barcha guruhlar, testlar,
o'quvchilar va natijalar yo'qoladi va migratsiyani qaytadan ishga
tushirish kerak bo'ladi. Uni faqat toza boshdan boshlamoqchi bo'lganda
ishlating.

---

## 3. Kod o'zgargandan keyin

Compose'da source mount YO'Q — har o'zgarishda image qayta yig'iladi.

```bash
docker compose build          # servis nomisiz!
docker compose up -d
```

> **Tuzoq:** `api`, `bot`, `worker` — uchta ALOHIDA image, bitta
> Dockerfile'dan. `docker compose build api` faqat API'ni yangilaydi,
> bot va worker eski kodda qolib ketadi va nosozlik "sirli" ko'rinadi.
> Model yoki `app/services/` o'zgarsa — har doim servis nomisiz build qiling.

Migratsiya qo'shilgan bo'lsa (`app/alembic/versions/` da yangi fayl):

```bash
docker compose build
docker compose run --rm api alembic upgrade head
docker compose up -d
```

---

## 4. Loglar

```bash
docker compose logs -f bot            # bitta servis, jonli
docker compose logs -f api worker     # bir nechta
docker compose logs --tail 100 bot    # oxirgi 100 qator
```

Grafana orqali (qidiruv va filtr bilan): <http://127.0.0.1:3001>,
login `admin`, parol `.env` dagi `GRAFANA_ADMIN_PASSWORD`. Chap menyudan
**Explore** → data source **Loki** → so'rov `{service="bot"}` yoki
`{service="worker"}`.

---

## 5. Manzillar

| Nima | Manzil |
|---|---|
| Admin panel | <http://127.0.0.1:8000/admin> |
| API hujjati (Swagger) | <http://127.0.0.1:8000/docs> |
| Mini App (dashboard) | <http://127.0.0.1:8000/dashboard> |
| Health check | <http://127.0.0.1:8000/health> |
| Grafana | <http://127.0.0.1:3001> |
| Postgres | `127.0.0.1:5433` |
| Redis | `127.0.0.1:6380` |

Postgres va Redis portlari faqat lokal interfeysda. Serverda ishlayotgan
bo'lsangiz SSH tunnel bilan oching:

```bash
ssh -L 8000:127.0.0.1:8000 -L 3001:127.0.0.1:3001 user@server
```

---

## 6. Testlar

```bash
docker compose run --rm api pytest app/tests -q
docker compose run --rm api pytest app/tests/test_access.py -v    # bitta fayl
```

`.env` da `INSTALL_DEV=false` bo'lsa image'da pytest bo'lmaydi. Dev
mashinada `INSTALL_DEV=true` turishi kerak.

Admin panel (lokal Node kerak):

```bash
cd admin-ui && npm run typecheck && npm run build
```

---

## 7. Bazaga so'rov yuborish

```bash
docker compose exec -T postgres psql -U omruser -d omrdb -c "SELECT count(*) FROM attempts;"
```

Interaktiv rejim:

```bash
docker compose exec postgres psql -U omruser -d omrdb
```

---

## 8. Admin panel frontendi ustida ishlash (dev rejimi)

Har o'zgarishda Docker build qilmaslik uchun Vite dev-serveri:

```bash
cd admin-ui
cp .env.example .env.local      # bir marta
npm install                     # bir marta
npm run dev
```

Panel <http://localhost:5173> da ochiladi va `/api` so'rovlarini
`http://localhost:8000` ga proksi qiladi. Backend (`docker compose up -d`)
ishlab turishi kerak.

---

## 9. Ixtiyoriy: Celery monitoringi

Flower standart profilda ko'tarilmaydi:

```bash
docker compose --profile monitoring up -d flower   # http://127.0.0.1:5555
```

---

## Tez-tez uchraydigan muammolar

**`docker compose` "REDIS_PASSWORD .env da belgilanishi shart" deb yiqiladi.**
`.env` da `REDIS_PASSWORD`, `POSTGRES_PASSWORD` yoki `GRAFANA_ADMIN_PASSWORD`
yo'q. Bu ataylab qilingan: parolsiz Redis'ga istalgan kishi task yubora
oladi. `.env.example` dan nusxa olib to'ldiring.

**Bot javob bermayapti.** `docker compose logs --tail 50 bot` ga qarang.
Ko'p uchraydigan sabab: `BOT_TOKEN` noto'g'ri yoki revoke qilingan
(loglarda `Unauthorized`), yoki bot konteyneri to'xtagan (`docker compose ps`).

**Botda "Dashboard" tugmasi ko'rinmayapti.** `.env` da `WEB_APP_URL` bo'sh.
Telegram Mini App uchun HTTPS manzil kerak, lokalda bu odatda ngrok
tunneli: `WEB_APP_URL=https://xxxx.ngrok-free.app`. Keyin
`docker compose up -d bot`.

**Admin panelga kira olmayapman.** Panelda parol yo'q — kirish Telegram
orqali (bot bir martalik kod yuboradi). Ikki shart: foydalanuvchining
`users.admin_role` bazada to'ldirilgan bo'lishi va `SECRET_KEY` namunaviy
bo'lmasligi. Birinchi adminni belgilash:

```bash
docker compose exec -T postgres psql -U omruser -d omrdb \
  -c "UPDATE users SET admin_role = 'SUPERADMIN' WHERE telegram_id = <SIZNING_ID>;"
```

**Skan tekshirilmayapti, natija kelmayapti.** Worker o'chgan bo'lishi
mumkin: `docker compose ps worker` va `docker compose logs -f worker`.
Task navbatda qolgan bo'lsa Redis ishlayotganini tekshiring.

**Port band ("port is already allocated").** O'sha portni boshqa dastur
egallagan. `.env` da `API_BIND_HOST` ni o'zgartiring yoki
`docker-compose.yml` dagi port raqamini almashtiring.

**Kod o'zgartirdim, lekin hech narsa o'zgarmadi.** Rebuild qilmagansiz
yoki faqat bitta servisni build qilgansiz. 3-bo'limga qarang.

**Hammasini toza boshdan boshlash.** Diqqat, barcha ma'lumot o'chadi:

```bash
docker compose down -v
docker compose build
docker compose up -d postgres redis
docker compose run --rm api alembic upgrade head
docker compose up -d
```
