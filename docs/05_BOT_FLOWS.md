# 05 — Bot Oqimlari (aiogram 3.x)

## Foydalanuvchi turlari
- **Ustoz**: /start qilgan har kishi (default). Guruh, o'quvchi, test boshqaradi.
- **Admin**: ADMIN_TELEGRAM_IDS dagi. Hammasini ko'radi (ixtiyoriy).
- **O'quvchi**: ko'pincha botda hisob ochmaydi — ustoz nomidan qo'shiladi.
  Lekin xohlasa botga ulanib o'z natijalari tarixini ko'rishi mumkin (kelajak).

## Asosiy menyu (ustoz)
```
/start
[📁 Mening guruhlarim]  [➕ Guruh yaratish]
[📝 Testlar]            [📊 Natijalar]
[ℹ️ Yordam]
```

## FSM holatlari (states.py)
```
GroupCreate: waiting_name
StudentAdd:  waiting_names         # bir nechta ism, har qatorga bitta
TestCreate:  waiting_title -> choosing_qcount -> choosing_vcount
             -> entering_key -> confirm
KeyEntry:    waiting_answers        # "ABCDA BACDB ..." yoki 1-A 2-C ...
```

## Oqim 1 — Guruh va o'quvchilar
```
[➕ Guruh yaratish] -> "Guruh nomini yuboring:" -> nom -> saqlanadi
Guruhni tanlash -> [👥 O'quvchilar] [➕ O'quvchi qo'shish] [📝 Test berish]
[➕ O'quvchi qo'shish] -> "Har qatorga bitta F.I.Sh yuboring:" ->
   "Ali Valiyev\nVali Aliyev\n..." -> bir nechta student yaratiladi
```

## Oqim 2 — Test yaratish
```
[📝 Test berish] (guruh tanlangan holatda)
 -> "Test nomi?" -> title
 -> inline: [40] [50] [90]            -> question_count
 -> inline: [4 variant (A-D)] [5 (A-E)] -> variant_count
 -> "To'g'ri javoblarni yuboring. Masalan:
     ABCD ABCD ... (probel bilan) yoki har qatorga: 1 A"
 -> javoblar parse qilinadi, soni qcount ga teng tekshiriladi
 -> ko'rsatiladi: "40 ta javob qabul qilindi ✅. Tasdiqlaysizmi?" [Ha][Yo'q]
 -> tasdiq -> test saqlanadi
 -> "Titullarni generatsiya qilaymi?" [Ha, hammasi] [Keyinroq]
```
### Kalit parse
```python
# Variant 1: "ABCDABCD..." yoki probel/qator bilan ajratilgan harflar
# Variant 2: "1 A", "2-C", "3:B" kabi nomerlangan
# -> {"1":"A","2":"B",...}; uzunlik == question_count bo'lishi shart
```

## Oqim 3 — Titul generatsiya
```
[Ha, hammasi] ->
   "⏳ N ta titul tayyorlanmoqda..."  (Celery pdf_task har student uchun)
   tayyor bo'lgach:
   - har titulni alohida hujjat (PDF) qilib yuborish
   - yoki bitta ZIP qilib yuborish  (inline: [Alohida] [ZIP])
```
> Katta guruhda ZIP qulay. Alohida — kichik guruhda.

## Oqim 4 — Javoblarni qabul qilish (o'quvchi/ustoz skan yuboradi)
Bot rasm (photo yoki document image) yoki PDF qabul qiladi. **Caption shart emas**
— QR orqali qaysi titul ekani aniqlanadi.
```
Foydalanuvchi -> [rasm/PDF yuboradi]
Bot -> "⏳ Tekshirilmoqda..."  (Celery omr_task)
   omr_task:
     - QR o'qish -> titul_uuid -> titul/test/student
     - OMR pipeline -> detected
     - grade(detected, test.answer_key) -> attempt saqlanadi
Bot natija:
   "📄 Test: {title}\n👤 {student}\n✅ To'g'ri: 34/40 (85%)\n"
   needs_review bo'lsa: "⚠️ Ba'zi belgilar noaniq, ustoz tekshirsin."
   + (ixtiyoriy) debug rasm
```
### Bir nechta varaq bittada
- Foydalanuvchi bir nechta rasm/PDF (yoki ko'p sahifali PDF) yuborsa:
  - **media group** (album) -> hammasini navbatga qo'yib, har biriga alohida
    natija + oxirida jamlama.
  - Ko'p sahifali PDF -> har sahifa alohida varaq sifatida ishlanadi.
```
Bot jamlama:
  "📊 5 ta varaq qayta ishlandi:
   • Ali V. — 34/40
   • Vali A. — 30/40
   • ... (1 ta noaniq ⚠️)"
```

## Oqim 5 — Natijalar / Tarix
```
[📊 Natijalar] -> guruh tanla -> test tanla ->
   "Test: {title}\nO'rtacha: 78%\nEng yuqori: 95%\n" + ro'yxat
   yoki Excel/CSV eksport (ixtiyoriy)

O'quvchi tarixi: o'quvchi tanla ->
   "Ali Valiyev tarixi:
    • Matem-1: 34/40 (85%) — 12.05
    • Fizika-2: 28/50 (56%) — 19.05 ..."
```

## Xatolar (o'quvchiga tushunarli xabarlar)
| Holat | Xabar |
|---|---|
| QR yo'q | "Varaqdagi QR kod o'qilmadi. To'liq, aniq suratga oling." |
| Anchor topilmadi | "Varaq burchaklari ko'rinmayapti. Butun varaqni kadrga oling." |
| Noto'g'ri fayl turi | "Iltimos rasm yoki PDF yuboring." |
| Titul DB'da yo'q | "Bu varaq tizimda topilmadi (eski yoki boshqa bot)." |

## Texnik
- aiogram 3.x, Redis FSM storage.
- Fayl yuklash: `bot.download` -> vaqtinchalik papka -> Celery task'ga yo'l beriladi.
- Uzoq ishlar Celery'da; bot darhol "⏳" yozadi, task tugagach natijani
  `bot.send_message` bilan yuboradi (task ichidan yoki callback orqali).
