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
# 2-bosqich: Python ilovasi (API / bot / worker uchun umumiy)
# ──────────────────────────────────────────────────────────────────────
FROM python:3.11-slim AS base

# System dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    # WeasyPrint needs (Debian trixie compatible package names)
    libpango-1.0-0 \
    libpangocairo-1.0-0 \
    libgdk-pixbuf-xlib-2.0-0 \
    libffi-dev \
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
    # Build tools
    gcc \
    python3-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Ilova root bilan ISHLAMAYDI. Foydalanuvchi shu yerda yaratiladi, lekin
# konteyner root bilan boshlanadi — entrypoint volume egaligini
# to'g'rilab, keyin `gosu` bilan shu foydalanuvchiga o'tadi.
RUN useradd --system --uid 10001 --create-home --shell /usr/sbin/nologin appuser

# Install Python deps first (cache layer) — manba nusxalanishidan oldin,
# shunda kodni o'zgartirganda bog'liqliklar qaytadan o'rnatilmaydi.
# INSTALL_DEV=false — prod image'ga pytest va boshqa test bog'liqliklari
# tushmaydi (compose `.env` dagi INSTALL_DEV orqali uzatadi).
COPY pyproject.toml .
ARG INSTALL_DEV=true
RUN if [ "$INSTALL_DEV" = "true" ]; then \
        pip install --no-cache-dir -e ".[dev]"; \
    else \
        pip install --no-cache-dir -e "."; \
    fi

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

ENTRYPOINT ["/usr/local/bin/docker-entrypoint.sh"]

# Default command (overridden per service in compose)
CMD ["uvicorn", "app.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
