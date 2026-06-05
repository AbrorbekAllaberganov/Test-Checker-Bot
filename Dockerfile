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
    # Build tools
    gcc \
    python3-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python deps first (cache layer)
COPY pyproject.toml .
RUN pip install --no-cache-dir -e ".[dev]"

# Copy source
COPY . .

# Create data directories
RUN mkdir -p /data/pdfs /data/debug /tmp/omr_uploads

ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

# Default command (overridden per service in compose)
CMD ["uvicorn", "app.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
