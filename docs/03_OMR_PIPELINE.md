# 03 — OMR Pipeline (Dumaloqlarni o'qish)

Bu loyihaning eng muhim va eng nozik qismi. Ustoz/o'quvchi qog'ozni qo'lda
to'ldirgani uchun skan qiyshiq, soya bilan, turli yorug'likda bo'ladi.
Shuning uchun **anchor-markerli fixed-grid** usuli ishlatiladi.

## Nima uchun anchor

Yuborilgan namuna shablonlarda burchak markerlari yo'q. Biz titulni **o'zimiz
generatsiya qilamiz**, shuning uchun varaqning 4 burchagiga **to'q qora to'ldirilgan
kvadratlar** (anchor / fiducial) qo'shamiz. Skanda ularni topib, perspektivani
to'g'rilaймiz (warp). Shundan keyin har dumaloqning joyi DOIM bir xil
piksel-koordinatada bo'ladi -> ishonchli o'qish.

## To'liq oqim

```
1. INPUT          rasm (jpg/png) yoki PDF sahifa
2. NORMALIZE      grayscale, kerak bo'lsa pdf->image (PyMuPDF, ~200 DPI)
3. QR DECODE      pyzbar -> "OMR|v1|<uuid>"  -> qaysi titul/test/student
4. FIND ANCHORS   4 ta qora kvadratni top, markazlarini ol
5. WARP           getPerspectiveTransform -> sobit o'lchamga (masalan 1654x2339, A4@200dpi)
6. LOAD LAYOUT    test turiga (40/50/90) mos grid koordinata jadvali
7. READ BUBBLES   har savol uchun har variant doirasini o'lcha (to'ldirilgan %)
8. DECIDE         eng to'q variant tanlanadi; ikkilik/bo'sh -> flag
9. GRADE          answer_key bilan solishtir -> score, detail, needs_review
10. DEBUG         (ixtiyoriy) annotatsiyalangan rasm saqla
```

## 1-2. Tayyorlash

```python
# PDF bo'lsa
import fitz  # PyMuPDF
def pdf_to_images(path, dpi=200):
    doc = fitz.open(path)
    for page in doc:
        pix = page.get_pixmap(dpi=dpi)
        yield np.frombuffer(pix.samples, np.uint8).reshape(pix.h, pix.w, pix.n)
```
- Rasmni grayscale -> Gaussian blur (kichik) -> adaptiv yoki Otsu threshold.

## 3. QR o'qish

```python
from pyzbar.pyzbar import decode
def read_qr(gray):
    for d in decode(gray):
        s = d.data.decode()
        if s.startswith("OMR|v1|"):
            return s.split("|")[2]   # uuid
    return None
```
- QR topilmasa: attempt status='error', error_msg='QR not found',
  o'quvchiga "Varaq QR kodi o'qilmadi, aniqroq suratga oling" deb javob.

## 4. Anchorlarni topish

Anchorlar — varaqning 4 burchagidagi to'ldirilgan qora kvadratlar (masalan
12x12 mm). Algoritm:
```
- threshold (qora = oq fonda)
- findContours
- approxPolyDP -> 4 burchakli, ~kvadrat (aspect ~1), maydon oraliqda
- 4 ta eng katta mos kvadratni ol
- markazlari bo'yicha tartibla: TL, TR, BR, BL (sum/diff usuli)
```
```python
def order_points(pts):
    # pts: 4x2
    s = pts.sum(1); d = np.diff(pts, axis=1).ravel()
    tl = pts[np.argmin(s)]; br = pts[np.argmax(s)]
    tr = pts[np.argmin(d)]; bl = pts[np.argmax(d)]
    return np.array([tl, tr, br, bl], dtype="float32")
```
Agar 4 ta topilmasa -> needs_review=true va eng yaxshi taxmin bilan davom etish
yoki xato qaytarish (konfiguratsiya).

## 5. Perspektivani to'g'rilash (warp)

```python
W, H = 1654, 2339   # A4 @ ~200 DPI portrait
dst = np.array([[0,0],[W-1,0],[W-1,H-1],[0,H-1]], "float32")
M = cv2.getPerspectiveTransform(order_points(anchor_centers), dst)
warped = cv2.warpPerspective(gray, M, (W, H))
```
Endi warped'da har element sobit koordinatada.

## 6. Layout jadvali (eng kritik konfiguratsiya)

Har test turi uchun har dumaloqning markazi `(x, y)` va radiusi `r` warped
koordinatada saqlanadi. Bu **titul HTML generatsiyasi bilan birga** belgilanadi —
ya'ni HTML qaysi joyga doira chizsa, layout shu joyni o'qiydi. Ikkalasi bitta
manbadan (masalan `layout.py` dagi `LAYOUTS` dict) hosil bo'lishi kerak, shunda
ikkisi sinxron qoladi.

Tuzilma:
```python
# bir nechta blok bo'ladi (A(1-20), B(21-40) ...). Har blok ustun.
LAYOUTS = {
  40: {
    "size": (1654, 2339),
    "options": ["A","B","C","D"],
    "blocks": [
       # har blok: birinchi savol nomeri, savollar soni,
       # birinchi savol birinchi variant markazi, qatorlar oralig'i (dy),
       # variantlar oralig'i (dx), radius
       {"start": 1,  "count": 20, "x0": 300, "y0": 760, "dx": 70, "dy": 58, "r": 18},
       {"start": 21, "count": 20, "x0": 760, "y0": 760, "dx": 70, "dy": 58, "r": 18},
    ],
  },
  50: { ... 2 blok x 25 ... },
  90: { ... 3 blok x 30 ... },
}
```
> Aniq raqamlar HTML shabloni bilan kalibrlanadi (04 ga qarang). Birinchi versiyada
> namuna PDF generatsiya qilib, debug rejimda doiralar to'g'ri tushganini tekshirish
> shart. `OMR_DEBUG=true` da har o'lchangan doira annotatsiya qilinadi.

Markaz hisoblash:
```python
def bubble_center(b, q_index_in_block, opt_index):
    x = b["x0"] + opt_index * b["dx"]
    y = b["y0"] + q_index_in_block * b["dy"]
    return x, y
```

## 7. Dumaloqni o'lchash

Har doira markazi atrofidan kichik ROI olinadi va to'ldirilganlik darajasi
("fill ratio") hisoblanadi:
```python
def fill_ratio(warped_bin, cx, cy, r):
    # warped_bin: 0/255 (to'ldirilgan = oq bo'lsin -> invert qilingan)
    mask = np.zeros_like(warped_bin)
    cv2.circle(mask, (cx, cy), int(r*0.8), 255, -1)
    area = cv2.countNonZero(mask)
    filled = cv2.countNonZero(cv2.bitwise_and(warped_bin, mask))
    return filled / max(area, 1)
```

## 8. Variant tanlash (qaror)

Har savol uchun 4 (yoki N) variantning fill_ratio'lari olinadi:
```
ratios = [rA, rB, rC, rD]
max1, max2 = eng katta va ikkinchi katta
- agar max1 < FILL_MIN (masalan 0.35):  bo'sh -> answer = None, flag="blank"
- agar (max1 - max2) < MARGIN (masalan 0.15): ikkilanish -> eng kattasini ol,
        flag="ambiguous", needs_review=true
- aks holda: answer = argmax, conf = max1 - max2
```
Konstantalar `.env` yoki settings'da, namuna skanlar bilan kalibrlanadi.

## 9. Baholash

```python
def grade(detected: dict, key: dict):
    total = len(key); score = 0; detail = {}
    for q, correct in key.items():
        got = detected.get(q)
        ok = (got == correct)
        score += int(ok)
        detail[q] = {"got": got, "key": correct, "ok": ok}
    return score, total, round(100*score/total, 2), detail
```
`needs_review` = biror savolda flag bo'lsa true.

## 10. Debug

`OMR_DEBUG=true` bo'lsa warped rasm ustiga:
- topilgan anchorlar (yashil)
- har doira (tanlangani — qizil to'ldirilgan, qolgani — ko'k chiziq)
- savol nomeri
chiziladi va `attempts.debug_file` ga saqlanadi. Bu kalibrlash uchun juda muhim.

## Aniqlikni oshirish bo'yicha maslahatlar

- Anchorlarni katta va to'q qil; varaq chetidan biroz ichkari.
- HTML'da doiralar orasini yetarlicha ochiq qil (zich bo'lsa ROI aralashadi).
- Doira ichiga juda och kulrang yo'naltiruvchi nuqta qo'yma (fill_ratio buzadi).
- Skan yo'riqnomasi: tekis joyda, soyasiz, butun varaq kadrda.
- Birinchi reliz: faqat namuna 40-talikni mukammal qil, keyin 50/90 ga ko'chir.

## Test ma'lumotlari

`app/tests/fixtures/` ga qo'lda to'ldirilgan namuna skanlar (turli burchak,
yorug'lik) qo'yiladi va kutilgan javoblar bilan solishtiriladi (regression test).
