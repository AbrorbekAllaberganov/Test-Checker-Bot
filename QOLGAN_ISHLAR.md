# Qo'lda bajariladigan ishlar (FAZA 0 dan keyin)

Kod tayyor, lekin **quyidagi ishlarni faqat siz qila olasiz** — ular
BotFather, server `.env` fayli va sizning qaroringiz bilan bog'liq.

Tuzilgan: 2026-09-16. Tegishli tasklar: `tasks.md` → T-01 … T-05.

> ⚠️ **Eng muhimi:** server `.env` fayliga yangi o'zgaruvchilar qo'shilmasa
> `docker compose` **ataylab ishga tushmaydi**. Bu xavfsiz nosozlik —
> eski konteynerlar ishlashda davom etadi, lekin deploy yiqiladi.
> Shu sababli 2-qadamni push qilishdan **oldin** bajaring.

---

## Tartib (shu ketma-ketlikda)

```
1. Server .env ni tayyorlash   (botga ta'sir qilmaydi)
2. Lokal .env ni tayyorlash    (botga ta'sir qilmaydi)
3. Tokenni revoke qilish       (bot shu daqiqada to'xtaydi)
4. Yangi tokenni .env ga yozish
5. Push → CI → deploy          (bot yangi token bilan qaytadi)
6. Tekshirish
```

3-qadamdan 5-qadamgacha bot ishlamaydi. Bu odatda bir necha daqiqa.
Foydalanuvchilar kam bo'lgan vaqtni tanlang.

---

## 1-qadam · Server `.env` ga yangi o'zgaruvchilar

- [ ] Serverga kiring va `.env` ning zaxirasini oling:

```bash
ssh user@server
cd /var/www/omr-test-bot
cp .env .env.backup-$(date +%F)
```

- [ ] Parollarni generatsiya qiling (har biri uchun **alohida** ishga tushiring):

```bash
python3 -c "import secrets; print(secrets.token_hex(16))"
```

> Parolda faqat harf va raqam bo'lsin. `$`, `@`, `#`, probel kabi belgilar
> compose buyruq qatorida va Redis URL'ida noto'g'ri talqin qilinadi.

- [ ] `.env` oxiriga quyidagilarni qo'shing (`nano .env`):

```
# --- FAZA 0 da qo'shilgan majburiy o'zgaruvchilar ---
REDIS_PASSWORD=<generatsiya qilingan parol>
GRAFANA_ADMIN_PASSWORD=<boshqa parol>
API_BIND_HOST=127.0.0.1
TRUSTED_PROXY_IPS=127.0.0.1
INSTALL_DEV=false
```

- [ ] `.env` dagi mavjud `REDIS_URL` qatorini **tahrirlang** — parolni
      URL ichiga ham qo'shish kerak (compose `env_file` ichida `${...}` ni
      kengaytirmaydi, shuning uchun ikki joyda yoziladi):

```
REDIS_URL=redis://:<yuqoridagi REDIS_PASSWORD>@redis:6379/0
```

- [ ] `INTERNAL_API_KEY` hali namunaviy bo'lsa (`change-me-...`), yangilang:

```
INTERNAL_API_KEY=<token_hex(32) natijasi>
```

- [ ] `SECRET_KEY` namunaviy bo'lsa admin panel ishlamaydi. Yangilang:

```
SECRET_KEY=<boshqa token_hex(32) natijasi>
```

### `POSTGRES_PASSWORD` haqida

Uni **o'zgartirmasangiz hech narsa qilish shart emas** — mavjud qiymat
(`omrpass`) joyida qolaveradi va hammasi ishlaydi.

O'zgartirmoqchi bo'lsangiz, `.env` ni tahrirlash **yetarli emas**:
Postgres parolni faqat baza birinchi marta yaratilganda o'rnatadi.
Avval bazada o'zgartiring, keyin `.env` ni:

```bash
docker compose exec -T postgres psql -U omruser -d omrdb \
  -c "ALTER USER omruser PASSWORD '<yangi parol>';"
```

Keyin `.env` da uchta joyni bir xil yangi parolga keltiring:
`POSTGRES_PASSWORD`, `DATABASE_URL`, `SYNC_DATABASE_URL`.

---

## 2-qadam · Lokal `.env` (dev mashinangiz)

- [ ] Xuddi shu o'zgaruvchilarni lokal `.env` ga ham qo'shing.
      Farqi bitta: lokalda `INSTALL_DEV=true` qoldiring, aks holda
      image'ga `pytest` tushmaydi va testlar ishlamaydi.

```
REDIS_PASSWORD=<lokal parol>
REDIS_URL=redis://:<lokal parol>@redis:6379/0
GRAFANA_ADMIN_PASSWORD=<lokal parol>
API_BIND_HOST=127.0.0.1
TRUSTED_PROXY_IPS=127.0.0.1
INSTALL_DEV=true
```

- [ ] Tekshiring (Docker Desktop ishlab turgan bo'lsin):

```bash
docker compose config >/dev/null && echo "compose OK"
docker compose build
docker compose up -d postgres redis
docker compose run --rm api alembic upgrade head
docker compose run --rm api pytest app/tests -q
```

Bu buyruqlar men bajara olmagan yagona tekshiruv — mening mashinamda
Docker demoni ishlamayotgan edi. Agar shu yerda xato chiqsa, menga
xato matnini yuboring.

---

## 3-qadam · Bot tokenini revoke qilish 🔴

Bu **eng muhim** xavfsizlik qadami. Token `591d758` (birinchi commit) dan
beri repoda turibdi va hozir ham amal qiladi. Repo'ni ko'rgan har kim
botni to'liq boshqara oladi: xabarlarni o'qiydi, foydalanuvchilarga yozadi
va Mini App imzosini soxtalashtiradi.

- [ ] Telegram'da [@BotFather](https://t.me/BotFather) ni oching
- [ ] `/mybots` → botingizni tanlang → **API Token** → **Revoke current token**
- [ ] Yangi tokenni nusxalang

> Shu daqiqadan boshlab eski token ishlamaydi va bot to'xtaydi.
> 4 va 5-qadamlarni darhol bajaring.

---

## 4-qadam · Yangi tokenni joylashtirish

- [ ] Server `.env` da:

```
BOT_TOKEN=<BotFather bergan yangi token>
```

- [ ] Lokal `.env` da ham xuddi shunday.

- [ ] **Agar deploy xabarnomalari uchun ayni shu botdan foydalansangiz** —
      GitHub'dagi sirni ham yangilang:
      `Settings → Secrets and variables → Actions → TELEGRAM_BOT_TOKEN_DEPLOY`.
      Boshqa bot bo'lsa hech narsa qilish shart emas.

---

## 5-qadam · Deploy

- [ ] O'zgarishlarni commit qiling va push qiling:

```bash
git commit -m "fix(faza-0): sirlar, portlar, konteyner va deploy tartibi"
git push origin main
```

> O'zgarishlar allaqachon `git add` qilingan (staged). Commit qilinmagan —
> uni siz o'zingiz qilasiz.

Push'dan keyin GitHub Actions avtomatik ishga tushadi:

1. `test` job — token skani, image build, migratsiya, `pytest`, admin panel build
2. `deploy` job — faqat testlar o'tgach

- [ ] Actions sahifasida ikkala job yashil bo'lganini kuzating.

### Agar push qilmasdan qo'lda deploy qilmoqchi bo'lsangiz

```bash
cd /var/www/omr-test-bot
git pull origin main
docker compose build
docker compose up -d postgres redis
docker compose run --rm api alembic upgrade head
docker compose up -d api bot worker
docker compose ps
```

---

## 6-qadam · Tekshirish

- [ ] Konteynerlar ko'tarilgan va API sog'lom:

```bash
docker compose ps
curl -s http://127.0.0.1:8000/health
```

- [ ] Portlar tashqaridan yopiq. **Boshqa mashinadan** ishga tushiring
      (serverning o'zida emas):

```bash
nc -zv <server-ip> 5433    # Postgres  — ulanmasligi kerak
nc -zv <server-ip> 6380    # Redis     — ulanmasligi kerak
nc -zv <server-ip> 3001    # Grafana   — ulanmasligi kerak
```

- [ ] Redis parolsiz javob bermaydi:

```bash
docker compose exec redis redis-cli ping        # NOAUTH xatosi kutiladi
```

- [ ] Ilova root emas:

```bash
docker compose exec api id                      # uid=10001(appuser)
```

- [ ] `.env` image ichiga tushmagan:

```bash
docker compose exec api ls -la /app/.env        # "No such file" kutiladi
```

- [ ] Eski token o'lgan:

```bash
curl -s "https://api.telegram.org/bot<ESKI_TOKEN>/getMe"   # 401 kutiladi
```

- [ ] Botni Telegram'da sinab ko'ring: `/start`, guruh ochish, titul
      generatsiya, bitta varaqni skan qilish.

- [ ] Admin panel: `http://127.0.0.1:8000/admin` (uzoq serverda SSH tunnel
      orqali: `ssh -L 8000:127.0.0.1:8000 user@server`).

### Biror narsa buzilsa

```bash
cd /var/www/omr-test-bot
cp .env.backup-<sana> .env       # .env ni tiklash
git checkout <oldingi-commit-sha>
docker compose build
docker compose up -d api bot worker
```

Migratsiya qaytarilishi kerak bo'lsa: `docker compose run --rm api alembic downgrade -1`.

---

## 7-qadam · FAZA 1 tekshiruvi (tenant izolyatsiyasi)

FAZA 1 kodi yozilgan, lekin men ishga tushirib ko'ra olmadim (Docker yo'q).
Quyidagilarni deploy'dan keyin **ikki xil Telegram akkaunt** bilan tekshiring:
A — guruh/test egasi, B — begona ustoz (ham `/start` bosgan).

- [ ] Avtomatik testlar o'tdi (CI `test` job yashil, yoki lokalda):

```bash
docker compose run --rm api pytest app/tests -q
# ayniqsa: app/tests/test_access.py
```

- [ ] **Mini App (B akkauntdan).** Brauzer DevTools yoki `curl` bilan A ning
      obyektlariga murojaat — hammasi `404` bo'lishi kerak:

```bash
# <B_INITDATA> — B akkaunt Mini App'ining initData qatori (DevTools → Network → Authorization header)
H='Authorization: tma <B_INITDATA>'
curl -s -o /dev/null -w "%{http_code}\n" -H "$H" https://<domen>/api/web/groups/<A_guruh_id>       # 404
curl -s -o /dev/null -w "%{http_code}\n" -H "$H" https://<domen>/api/web/tests/<A_test_id>         # 404
curl -s -o /dev/null -w "%{http_code}\n" -H "$H" https://<domen>/api/web/attempts/<A_attempt_id>   # 404
curl -s -H "$H" https://<domen>/api/web/groups                                                    # faqat B guruhlari
```

- [ ] **Bot (B akkauntdan).** Botda o'z menyusida yurib, A ning guruh/test/
      natijalarini ko'rmasligini tekshiring. Soxta callback yuborish oddiy
      Telegram klientidan iloji yo'q — shuning uchun bu qism `test_access.py`
      servis testlari bilan qoplanadi.

- [ ] **Skan egaligi.** A o'z titulini chop etib, B akkauntdan shu varaqni
      skan qiling → B ga "Bu varaq sizning testingizga tegishli emas" kelishi
      kerak; A ning natijalarida yangi urinish paydo BO'LMASLIGI kerak.
      Admin panel → Skanlar'da bu urinish `error` holatida
      ("Titul boshqa ustozga tegishli") ko'rinadi.

- [ ] **Ro'yxatsiz akkaunt.** `/start` bosmagan yangi akkauntdan rasm yuboring
      → "ro'yxatdan o'ting: /start" xabari, `attempts` ga yozuv yo'q.

- [ ] **Statik fayllar yopilgan:**

```bash
curl -s -o /dev/null -w "%{http_code}\n" https://<domen>/static/pdfs/titul_1_1.pdf   # 404
curl -s -o /dev/null -w "%{http_code}\n" https://<domen>/static/uploads/x.jpg        # 404
```

- [ ] **Rasmlar hali ham ko'rinadi.** Mini App'da urinish tafsilotini oching —
      varaq surati (va `OMR_DEBUG=true` bo'lsa annotatsiya) yuklanishi kerak.
      Admin panel → Skanlar → inspektorda ham. Ikkalasi endi auth'li
      endpointdan blob sifatida yuklaydi; xato bo'lsa "Rasm topilmadi yoki
      yuklanmadi" chiqadi va brauzer konsolida sabab ko'rinadi.

- [ ] **Yangi PDF nomi.** Yangi titul generatsiya qiling — fayl nomi
      `titul_<uuid>.pdf` bo'lishi kerak (`ls /data/pdfs` konteyner ichida).
      Eski `titul_<id>_<id>.pdf` fayllar joyida qoladi va bot ular bilan
      ishlashda davom etadi (`tituls.pdf_path` bazada).

---

## Sizning qaroringizni kutayotgan savol

**Git tarixini qayta yozamizmi?**

Token eski commitlarda qolgan. Uni tarixdan butunlay o'chirish uchun
`git filter-repo` kerak, lekin bu barcha commit SHA'larini o'zgartiradi
va mavjud klonlarni sindiradi.

Mening tavsiyam: **kerak emas.** Token revoke qilingach tarixdagi nusxa
oddiy foydasiz satrga aylanadi. Tarixni qayta yozish xavfi foydasidan
katta. Agar repo ochiq (public) bo'lsa yoki talab shunday bo'lsa — ayting,
qadamlarini yozib beraman.

---

## Keyingi qadam

FAZA 0 yopilgach navbat **FAZA 1** ga keladi — tenant izolyatsiyasi
(IDOR). Bu eng jiddiy qolgan muammo: hozir istalgan ro'yxatdan o'tgan
ustoz boshqa ustozning javob kalitlarini, natijalarini va o'quvchilarini
ko'radi hamda o'zgartiradi. Tafsilotlar `tasks.md` → T-06 … T-10.

FAZA 1 ni boshlashdan oldin `tasks.md` ning "Foydalanuvchi qarori kerak
bo'lgan bandlar" bo'limidagi savollarga javob bersangiz ish uzluksiz
boradi.
