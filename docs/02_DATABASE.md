# 02 — Ma'lumotlar Bazasi (PostgreSQL)

## ER (qisqacha)

```
users (ustoz/admin)
  └─< groups
        └─< students
tests (guruhga tegishli)
  ├─ answer_key (JSON: to'g'ri javoblar)
  └─< tituls (har student+test uchun bitta titul/varaq)
        └─< attempts (yuborilgan skan natijasi)
```

## Jadval ta'riflari

### users
Telegram orqali kiradigan odam (asosan ustoz).
```sql
CREATE TABLE users (
    id              BIGSERIAL PRIMARY KEY,
    telegram_id     BIGINT UNIQUE NOT NULL,
    full_name       TEXT,
    username        TEXT,
    role            TEXT NOT NULL DEFAULT 'teacher',  -- 'teacher' | 'admin'
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

### groups
Ustoz ochadigan guruh.
```sql
CREATE TABLE groups (
    id          BIGSERIAL PRIMARY KEY,
    owner_id    BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    name        TEXT NOT NULL,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_groups_owner ON groups(owner_id);
```

### students
Guruhdagi o'quvchi. Telegram_id ixtiyoriy (o'quvchi botda bo'lmasligi mumkin —
ustoz nomidan qo'shadi). Agar o'quvchi botga ulansa, telegram_id biriktiriladi.
```sql
CREATE TABLE students (
    id          BIGSERIAL PRIMARY KEY,
    group_id    BIGINT NOT NULL REFERENCES groups(id) ON DELETE CASCADE,
    full_name   TEXT NOT NULL,
    telegram_id BIGINT,                 -- ixtiyoriy
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_students_group ON students(group_id);
```

### tests
```sql
CREATE TABLE tests (
    id            BIGSERIAL PRIMARY KEY,
    group_id      BIGINT NOT NULL REFERENCES groups(id) ON DELETE CASCADE,
    title         TEXT NOT NULL,
    question_count INT NOT NULL,        -- 40 | 50 | 90
    variant_count  INT NOT NULL DEFAULT 4,  -- A,B,C,D
    -- to'g'ri javoblar: {"1":"A","2":"C",...}  index 1-based string
    answer_key    JSONB NOT NULL,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT chk_qcount CHECK (question_count IN (40,50,90))
);
CREATE INDEX idx_tests_group ON tests(group_id);
```

### tituls
Har (test, student) juftligi uchun bitta varaq + QR. QR ichida shu titul UUID.
```sql
CREATE TABLE tituls (
    id          BIGSERIAL PRIMARY KEY,
    uuid        UUID UNIQUE NOT NULL DEFAULT gen_random_uuid(),  -- QR ichida shu
    test_id     BIGINT NOT NULL REFERENCES tests(id) ON DELETE CASCADE,
    student_id  BIGINT NOT NULL REFERENCES students(id) ON DELETE CASCADE,
    pdf_path    TEXT,                  -- generatsiya qilingan fayl
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (test_id, student_id)
);
CREATE INDEX idx_tituls_test ON tituls(test_id);
```
> QR payload formati: `OMR|v1|<titul_uuid>` (03 ga qarang). Faqat UUID yetarli —
> qolgan hammasi DB'dan olinadi. Bu PDF qayta generatsiyada ham barqaror.

### attempts
O'quvchi yuborgan skan natijasi. Bir titulga bir nechta urinish bo'lishi mumkin
(qayta yuborsa) — eng oxirgisi yoki eng yaxshisini ko'rsatamiz.
```sql
CREATE TABLE attempts (
    id            BIGSERIAL PRIMARY KEY,
    titul_id      BIGINT NOT NULL REFERENCES tituls(id) ON DELETE CASCADE,
    -- o'qilgan javoblar: {"1":"A","2":null,...}  null = bo'sh/aniqlanmadi
    detected      JSONB NOT NULL,
    score         INT,                 -- to'g'ri javoblar soni
    total         INT,                 -- jami savol
    percent       NUMERIC(5,2),
    -- har savol bo'yicha holat (debug/qo'lda tekshirish uchun):
    -- {"3":{"got":"B","key":"A","ok":false,"conf":0.41,"flag":"low_conf"}}
    detail        JSONB,
    needs_review  BOOLEAN NOT NULL DEFAULT false,  -- past ishonch bo'lsa
    source_file   TEXT,                -- yuborilgan rasm/pdf
    debug_file    TEXT,                -- annotatsiyalangan debug rasm
    status        TEXT NOT NULL DEFAULT 'done', -- 'pending'|'done'|'error'
    error_msg     TEXT,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_attempts_titul ON attempts(titul_id);
CREATE INDEX idx_attempts_created ON attempts(created_at);
```

## Natijalar tarixi
Tarix = ma'lum o'quvchining barcha `attempts` lari `titul -> test` orqali.
So'rov misoli:
```sql
SELECT t.title, a.score, a.total, a.percent, a.created_at
FROM attempts a
JOIN tituls ti ON ti.id = a.titul_id
JOIN tests  t  ON t.id  = ti.test_id
WHERE ti.student_id = :student_id
ORDER BY a.created_at DESC;
```

## Migration
- Alembic ishlatiladi. `gen_random_uuid()` uchun `pgcrypto` extension:
  `CREATE EXTENSION IF NOT EXISTS pgcrypto;`
