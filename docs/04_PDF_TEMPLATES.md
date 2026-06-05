# 04 — Titul (Javoblar Varaqasi) PDF Shablonlari

3 ta HTML shablon: 40, 50, 90 talik. Yuborilgan namuna rasmlardagi umumiy
dizaynga mos: yuqorida sarlavha "JAVOBLAR VARAQASI", logo joylari, ko'rsatmalar,
to'ldirish namunasi, bloklar (A(1-20)/B(21-40) ...), familiya/ism maydonlari va
imzo. **Yangi qo'shilgani**: 4 burchakka qora anchor + QR code.

> Muhim tamoyil: HTML'dagi doiralar joylashuvi va `omr/layout.py` dagi grid
> koordinatalari **bitta haqiqat manbasidan** kelib chiqsin. Eng oson yo'l —
> doiralarni absolyut `position` bilan, layout dagi formula (x0,y0,dx,dy) bo'yicha
> joylashtirish. PDF renderer DPI sini bilib, layout pikselini hisoblash mumkin.

## Umumiy o'lcham

- A4 portrait: 210mm x 297mm
- Renderer: WeasyPrint (HTML/CSS -> PDF). 200 DPI da: 1654 x 2339 px.
- CSS `@page { size: A4; margin: 0 }`, hammasi mm yoki absolyut joylashuv.

## Anchorlar (4 ta)

- O'lchami ~10mm x 10mm to'ldirilgan qora kvadrat.
- Joylashuv: har burchakdan 8mm ichkarida.
- CSS:
```css
.anchor { position: absolute; width: 10mm; height: 10mm; background:#000; }
.anchor.tl { top: 8mm;  left: 8mm; }
.anchor.tr { top: 8mm;  right: 8mm; }
.anchor.br { bottom: 8mm; right: 8mm; }
.anchor.bl { bottom: 8mm; left: 8mm; }
```
> OMR warp shu 4 markaz orasidagi to'rtburchakka to'g'rilaydi. Demak layout
> koordinatalari ham shu to'rtburchak ichida (anchor markazlari = (8+5)=13mm
> chetdan) o'lchanadi. layout.py shuni hisobga oladi.

## QR code

- Joylashuv: yuqori-o'ng burchak yonida (anchor bilan ustma-ust tushmasin).
- O'lchami ~25mm x 25mm.
- Payload: `OMR|v1|<titul_uuid>`.
- Generatsiya: `qrcode` -> PNG -> base64 -> `<img>` ichiga, yoki vaqtincha fayl.

## Maydonlar (har titulda to'ldirilgan holda chiqadi)

- Test nomi (test.title)
- Guruh nomi (group.name)
- O'quvchi F.I.Sh (student.full_name)
- (Imzo joyi bo'sh qoladi — o'quvchi qo'lda imzolaydi)
> Eslatma: namuna rasmlarda o'quvchi familiyasini qo'lda yozadi. Bizda esa bot
> biladi, shuning uchun chop etilgan holda chiqaramiz (lekin OMR uchun ahamiyatsiz —
> ism QR orqali aniqlanadi).

## Bloklar tartibi

| Tur | Bloklar |
|---|---|
| 40 | A(1–20), B(21–40) — 2 ustun |
| 50 | A(1–25), B(26–50) — 2 ustun |
| 90 | Majburiy/Obyazatel + I blok + II blok yoki 3x30 — 3 ustun |

Har savol qatori: chapda nomer, o'ngda N ta doira (A,B,C,D) ustun bilan.

## Doira HTML (grid)

Har doira layout formulasiga mos absolyut joylashtiriladi:
```html
<div class="bubble"
     style="left: {x_mm}mm; top: {y_mm}mm; width:{d}mm; height:{d}mm;">A</div>
```
```css
.bubble {
  position:absolute; border:1.2pt solid #c0392b; border-radius:50%;
  display:flex; align-items:center; justify-content:center;
  font-size:7pt; color:#c0392b;  /* harf och rangda, fill_ratio ga ta'sir qilmasin */
}
```
> Doira chizig'i ham fill_ratio ga ozgina qo'shiladi — shuning uchun FILL_MIN ni
> bo'sh doira ratio sidan yuqori qo'yamiz (kalibrlash). Harfni juda och (masalan
> #e0a0a0) qil yoki doira tashqarisiga chiqar.

## base.html (umumiy qolib)

```html
<!doctype html><html><head><meta charset="utf-8">
<style>
@page { size: A4; margin: 0; }
body { margin:0; position:relative; width:210mm; height:297mm;
       font-family: 'DejaVu Sans', sans-serif; }
.anchor {...} .bubble {...}
.header {...} .meta {...} .qr {...}
</style></head>
<body>
  <div class="anchor tl"></div><div class="anchor tr"></div>
  <div class="anchor br"></div><div class="anchor bl"></div>
  <img class="qr" src="{{ qr_data_uri }}">
  <div class="header">JAVOBLAR VARAQASI</div>
  <div class="meta">
     <div>Test: {{ test_title }}</div>
     <div>Guruh: {{ group_name }}</div>
     <div>O'quvchi: {{ student_name }}</div>
  </div>
  <!-- bloklar: render.py jinja loop bilan doiralarni joylashtiradi -->
  {% for b in bubbles %}
    <div class="bubble" style="left:{{b.x}}mm;top:{{b.y}}mm;
         width:{{b.d}}mm;height:{{b.d}}mm;">{{b.letter}}</div>
  {% endfor %}
</body></html>
```

## render.py (PDF yaratish)

```python
from weasyprint import HTML
from jinja2 import Environment, FileSystemLoader
from app.omr.layout import build_bubble_positions  # mm da

def render_titul_pdf(titul, test, group, student, qr_data_uri, out_path):
    bubbles = build_bubble_positions(test.question_count, test.variant_count)
    tpl = env.get_template(f"titul_{test.question_count}.html")
    html = tpl.render(test_title=test.title, group_name=group.name,
                      student_name=student.full_name, qr_data_uri=qr_data_uri,
                      bubbles=bubbles)
    HTML(string=html).write_pdf(out_path)
```

## layout.py — yagona haqiqat manbasi

```python
# mm da grid; OMR layout shu mm ni px ga (dpi/25.4) aylantiradi.
LAYOUTS_MM = {
  40: {"options":["A","B","C","D"],
       "blocks":[{"start":1,"count":20,"x0":35,"y0":95,"dx":9,"dy":7.2,"d":6},
                 {"start":21,"count":20,"x0":95,"y0":95,"dx":9,"dy":7.2,"d":6}]},
  50: {...},
  90: {...},
}

def build_bubble_positions(qcount, vcount):
    L = LAYOUTS_MM[qcount]; out=[]
    for b in L["blocks"]:
        for i in range(b["count"]):
            for j,letter in enumerate(L["options"][:vcount]):
                out.append({"q": b["start"]+i, "letter":letter,
                    "x": b["x0"]+j*b["dx"], "y": b["y0"]+i*b["dy"], "d": b["d"]})
    return out

def omr_grid_px(qcount, dpi=200):
    # OMR pipeline shu funksiyadan markaz/radius oladi (px)
    k = dpi/25.4
    ...
```

> Shu tarzda PDF qayerga doira chizsa, OMR aynan shu yerni o'qiydi. Kalibrlashda
> faqat `LAYOUTS_MM` ni sozlash kifoya.
