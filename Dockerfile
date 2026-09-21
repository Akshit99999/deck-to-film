FROM python:3.11-slim-bookworm

# ── System deps ──────────────────────────────────────────────────────────────
RUN apt-get update && apt-get install -y --no-install-recommends \
    # ffmpeg + media tools
    ffmpeg \
    # LibreOffice for PPTX → PDF
    libreoffice \
    # poppler for pdftoppm
    poppler-utils \
    # git for shallow clone
    git \
    # Node.js 20 (Remotion)
    curl ca-certificates gnupg \
    # CJK + Indic fonts for captions
    fonts-noto \
    fonts-noto-cjk \
    fonts-noto-extra \
    # Playwright Chromium dependencies
    libnspr4 libnss3 libatk1.0-0 libatk-bridge2.0-0 libcups2 \
    libdrm2 libxkbcommon0 libxcomposite1 libxdamage1 libxfixes3 \
    libxrandr2 libgbm1 libasound2 libpango-1.0-0 libpangocairo-1.0-0 \
    libgtk-3-0 libx11-xcb1 \
    && rm -rf /var/lib/apt/lists/*

# ── Node.js 20 ────────────────────────────────────────────────────────────────
RUN curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get install -y nodejs \
    && rm -rf /var/lib/apt/lists/*

# ── Python package ────────────────────────────────────────────────────────────
WORKDIR /app
COPY pyproject.toml ./
COPY videogen/ ./videogen/
RUN pip install --no-cache-dir -e ".[dev]"

# ── Playwright Chromium ────────────────────────────────────────────────────────
RUN playwright install chromium --with-deps

# ── Remotion dependencies ─────────────────────────────────────────────────────
COPY remotion/ ./remotion/
RUN cd remotion && npm install

# ── Working volume ────────────────────────────────────────────────────────────
VOLUME ["/workspace"]
WORKDIR /workspace

ENTRYPOINT ["videogen"]
CMD ["--help"]
