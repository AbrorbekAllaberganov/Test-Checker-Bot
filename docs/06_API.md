# 06 — API (FastAPI)

Bot biznes-logikani servis qatlami orqali ishlatadi. Web kelajakda shu
endpointlardan foydalanadi. Birinchi relizda API ichki (internal) — bot bilan
bir kodbazada servislarni to'g'ridan-to'g'ri chaqirish ham mumkin.

## Auth
- Telegram WebApp `initData` tekshiruvi (web uchun) yoki ichki token.
- Birinchi reliz: faqat bot ishlatadi -> oddiy ichki API key (`X-Internal-Key`).

## Endpointlar

### Guruhlar
```
POST   /groups                {name}                      -> group
GET    /groups?owner_id=       -> [group]
GET    /groups/{id}
DELETE /groups/{id}
```

### O'quvchilar
```
POST   /groups/{id}/students   {full_names: [..]}          -> [student]
GET    /groups/{id}/students
DELETE /students/{id}
```

### Testlar
```
POST   /groups/{id}/tests      {title, question_count, variant_count, answer_key}
GET    /groups/{id}/tests
GET    /tests/{id}
PATCH  /tests/{id}             {answer_key?, title?}
```

### Titullar
```
POST   /tests/{id}/tituls/generate   -> Celery task id (har student uchun PDF)
GET    /tests/{id}/tituls            -> [{student, pdf_url, uuid}]
GET    /tituls/{uuid}/pdf            -> PDF fayl
```

### Skan / Attempt
```
POST   /attempts/scan
   multipart: file (image|pdf)
   -> Celery omr_task -> {task_id}
GET    /attempts/{id}                -> natija
GET    /tituls/{uuid}/attempts       -> shu varaq urinishlari
PATCH  /attempts/{id}                -> qo'lda tuzatish (needs_review hal qilish)
```

### Natijalar / Tarix
```
GET    /tests/{id}/results           -> [{student, score, percent, ...}] + stats
GET    /students/{id}/history        -> [{test_title, score, percent, date}]
GET    /tests/{id}/results/export    -> CSV/XLSX
```

## Servis qatlami (app/services) — bot ham, api ham chaqiradi
```
groups.create_group(owner_id, name)
students.add_students(group_id, names: list[str])
tests.create_test(group_id, title, qcount, vcount, key: dict)
tests.parse_key(text, qcount, options) -> dict
titul.generate_for_test(test_id) -> enqueue pdf_task per student
titul.qr_payload(titul_uuid) -> "OMR|v1|<uuid>"
grading.process_scan(file_path) -> enqueue omr_task
grading.grade(detected, key) -> (score,total,percent,detail,needs_review)
history.student_history(student_id)
history.test_results(test_id)
```

## Celery vazifalari (app/worker/tasks.py)
```
pdf_task(titul_id):
   - QR data uri yaratish
   - render_titul_pdf(...) -> pdf_path saqlash -> titul.pdf_path yangilash
   - tugagach botga "tayyor" signal (yoki bot poll qiladi)

omr_task(attempt_id | file_path, sender_chat_id):
   - rasm/pdf yuklash
   - pipeline.run(image) -> uuid, detected
   - titul/test topish -> grade -> attempt yozish
   - bot orqali natijani sender_chat_id ga yuborish
```
