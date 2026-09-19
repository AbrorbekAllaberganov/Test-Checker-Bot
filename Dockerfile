# ──────────────────────────────────────────────────────────────────────
# 1-bosqich: React admin panelini yig'ish
#
# Panel FastAPI tomonidan `/admin` manzilida statik fayl sifatida
# beriladi (app/api/main.py: _mount_admin_spa), shu sababli uni shu
# yerda yig'ib, tayyor `dist` ni yakuniy image'ga ko'chiramiz.
# Node runtime yakuniy image'ga TUSHMAYDI.
# ──────────────────────────────────────────────────────────────────────
FROM node:22-slim AS admin-ui-builder

WORKDIR /ui

# Avval faqat manifest — bog'liqliklar kesh qatlamida qoladi va
# manbani o'zgartirganda qaytadan o'rnatilmaydi.
COPY admin-ui/package.json admin-ui/package-lock.json* ./
RUN npm install --no-audit --no-fund

COPY admin-ui/ ./
RUN npm run build


# ──────────────────────────────────────────────────────────────────────
# 2-bosqich: Python bog'liqliklarini YIG'ISH (builder)
#
# `gcc` va `python3-dev` faqat shu yerda kerak (C kengaytmalari uchun).
# Yakuniy image'ga ular TUSHMAYDI — kompilyator prod konteynerda turishi
# hujumchining ishini osonlashtiradi va image'ni ~150 MB shishiradi
# (weaknesses.md №37).
# ──────────────────────────────────────────────────────────────────────
FROM python:3.11-slim AS python-builder

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    python3-dev \
    libffi-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Bog'liqliklar alohida prefiksga o'rnatiladi va keyin runtime'ga
# ko'chiriladi. `-e .` ishlatilmaydi: u manba papkasiga bog'lanib qoladi.
COPY pyproject.toml .
ARG INSTALL_DEV=true
RUN mkdir -p /install \
    && if [ "$INSTALL_DEV" = "true" ]; then \
        pip install --no-cache-dir --prefix=/install ".[dev]"; \
    else \
        pip install --no-cache-dir --prefix=/install "."; \
    fi


# ──────────────────────────────────────────────────────────────────────
# 3-bosqich: Ishlaydigan image (API / bot / worker uchun umumiy)
# ──────────────────────────────────────────────────────────────────────
FROM python:3.11-slim AS base

# Faqat RUNTIME kutubxonalari (kompilyatorsiz).
RUN apt-get update && apt-get install -y --no-install-recommends \
    # WeasyPrint needs (Debian trixie compatible package names)
    libpango-1.0-0 \
    libpangocairo-1.0-0 \
    libgdk-pixbuf-xlib-2.0-0 \
    libffi8 \
    libcairo2 \
    libxml2 \
    libxslt1.1 \
    # OpenCV needs
    libgl1 \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    # pyzbar needs (zbar library)
    libzbar0 \
    # WeasyPrint font support
    fonts-dejavu-core \
    # Huquqlarni tushirish uchun (docker/entrypoint.sh)
    gosu \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Ilova root bilan ISHLAMAYDI. Foydalanuvchi shu yerda yaratiladi, lekin
# konteyner root bilan boshlanadi — entrypoint volume egaligini
# to'g'rilab, keyin `gosu` bilan shu foydalanuvchiga o'tadi.
RUN useradd --system --uid 10001 --create-home --shell /usr/sbin/nologin appuser

# Builder'da o'rnatilgan paketlar (kesh qatlami — manbadan oldin).
COPY --from=python-builder /install /usr/local

# Copy source
COPY . .

# Yig'ilgan admin panel (1-bosqichdan)
COPY --from=admin-ui-builder /ui/dist ./admin-ui/dist

# Create data directories.
# Bo'sh named volume birinchi marta mount qilinganda Docker mount
# nuqtasidagi egalikni ko'chiradi — shu sababli yangi o'rnatishda
# entrypoint'ga chown qilishga ham to'g'ri kelmaydi.
RUN mkdir -p /data/pdfs /data/debug /tmp/omr_uploads \
    && chown -R appuser:appuser /data /tmp/omr_uploads /app

COPY docker/entrypoint.sh /usr/local/bin/docker-entrypoint.sh
RUN chmod +x /usr/local/bin/docker-entrypoint.sh

ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

# Image darajasidagi healthcheck — API uchun (compose'da servis bo'yicha
# aniqroq qiymatlar bilan qayta belgilanadi). `/health` DB va Redis'ni ham
# tekshiradi va nosozda 503 beradi (weaknesses.md №37).
HEALTHCHECK --interval=30s --timeout=5s --start-period=40s --retries=3 \
    CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=3).status == 200 else 1)" || exit 1

ENTRYPOINT ["/usr/local/bin/docker-entrypoint.sh"]

# Default command (overridden per service in compose)
CMD ["uvicorn", "app.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
