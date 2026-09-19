# 05 — Bot Oqimlari (aiogram 3.x)

> **Yangilangan:** 2026-09-19. Hujjat kod bilan solishtirib tekshirildi
> (weaknesses.md №36). Hali yozilmagan narsalar "Rejalashtirilgan" bo'limida.

## Foydalanuvchi turlari
- **Ustoz**: /start qilgan har kishi (default). Guruh, o'quvchi, test boshqaradi.
  `AccessMiddleware` uni birinchi xabarda yaratadi/yangilaydi va bloklanganini
  shu yerda to'xtatadi.
- **Admin**: ADMIN_TELEGRAM_IDS dagi. Admin PANELIGA kiradi (`/api/admin`);
  botda alohida admin menyusi YO'Q.
- **O'quvchi**: botda hisob ochmaydi — ustoz nomidan qo'shiladi.
  `students.telegram_id` ustuni bor, lekin uni to'ldiradigan oqim
  hozircha yozilmagan (pastga qarang).

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
   "⏳ N ta titul tayyorlanmoqda..."  (Celery tituls_batch_task — BITTA task)
   tayyor bo'lgach: barcha PDF'lar bitta ZIP bo'lib keladi
   (45 MB dan oshsa qismlarga bo'linadi)

[📄 Titullar] -> [Alohida] / [🗜 ZIP]
```
> **ZIP — standart yo'l.** Ilgari har titul alohida `pdf_task` +
> `send_document` edi: 150 o'quvchi = 150 ta xabar, Telegram flood limitiga
> urilib ba'zilari indamay yo'qolardi (weaknesses.md №22).
> "Alohida" varianti `TITUL_SINGLE_SEND_MAX` (standart 20) tagacha ishlaydi;
> undan ko'p bo'lsa bot ZIP ni tavsiya qiladi.

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
- **media group** (album) — hammasi navbatga qo'yiladi, har biriga alohida
  natija keladi.
- **Ko'p sahifali PDF** — faqat **1-sahifa** tekshiriladi va natija xabariga
  ogohlantirish qo'shiladi ("⚠️ Faylda N sahifa bor — faqat 1-sahifa
  tekshirildi"). Har sahifani alohida urinish qilish — alohida feature;
  cheklov ataylab: yuzlab sahifali PDF worker'ni OOM qilardi (№14, №23).

### Qabul qilinadigan formatlar
`image/jpeg`, `image/png`, `image/webp`, `image/tiff`, `application/pdf`.
**HEIC/HEIF rad etiladi** — OpenCV uni o'qiy olmaydi va skan har doim xato
berardi. Bot foydalanuvchiga suratni "fayl" emas, oddiy "photo" qilib
yuborishni yoki iPhone'da "Most Compatible" formatini yoqishni aytadi.

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
| Varaq yon burilgan | "Varaq yon tomonga burilgan. Uni to'g'ri (portret) holatda suratga oling." |
| Begona titul | "Bu varaq sizning testingizga tegishli emas." |
| Buzuq/katta fayl | "Varaqni o'qib bo'lmadi. ... qayta yuboring." (retry YO'Q) |
| Vaqtinchalik nosozlik | "Vaqtinchalik texnik nosozlik. Birozdan keyin qayta yuboring." |
| HEIC | "iPhone HEIC formati qo'llanmaydi..." |
| Limit tugadi | "🚫 Limit tugadi" (faqat `ENFORCE_QUOTA=true` bo'lganda) |

> Varaq **180° teskari** tushsa bot buni o'zi aniqlaydi (QR joylashuvi
> bo'yicha) va to'g'rilab o'qiydi — xato xabar bermaydi (№13).

## Rejalashtirilgan (kodda HOZIRCHA YO'Q)

Bu oqimlar loyiha g'oyasida bor, lekin hali yozilmagan — hujjatni kod bilan
adashtirmaslik uchun alohida ajratildi:

- **O'quvchining botga ulanishi.** `students.telegram_id` ustuni va
  `services/students.link_telegram()` mavjud, lekin ularni chaqiradigan
  handler yo'q. Dashboard'da o'quvchi doim "Ulanmagan".
- **O'quvchi o'z tarixini ko'rishi.** Yuqoridagisiga bog'liq.
- **Albom uchun jamlama xabar.** Hozir har varaq uchun alohida natija
  keladi; "📊 5 ta varaq qayta ishlandi: ..." ko'rinishidagi yakuniy
  jamlama yo'q.
- **Botda admin menyusi.** Admin amallari faqat web panelda.

## Texnik
- aiogram 3.x, Redis FSM storage.
- FSM holatlarida `F.text` filtri bor; matn bo'lmagan xabar `fsm_non_text`
  fallback'iga tushadi (holat tiqilib qolmaydi).
- Skan handlerlari `StateFilter(None)` bilan — FSM ichidagi rasm skan emas.
- Fayl yuklash: `bot.download` -> vaqtinchalik papka -> Celery task'ga yo'l beriladi.
- Uzoq ishlar Celery'da; bot darhol "⏳" yozadi, task tugagach natijani
  `bot.send_message` bilan yuboradi (task ichidan yoki callback orqali).
