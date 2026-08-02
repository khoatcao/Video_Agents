FROM python:3.11-slim

# ── System packages ────────────────────────────────────────────────────────────
# curl: used for health-check commands and downloading Node setup script
# ffmpeg: required by the Remotion renderer to encode video frames
# ca-certificates, gnupg: needed to verify the NodeSource apt repo signature
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    ffmpeg \
    ca-certificates \
    gnupg \
    && rm -rf /var/lib/apt/lists/*

# ── Node.js 20 (via NodeSource) ────────────────────────────────────────────────
RUN curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get install -y --no-install-recommends nodejs \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# ── Python dependencies ────────────────────────────────────────────────────────
# Copy only the project manifest first so this layer is cached independently
# from source changes.
COPY pyproject.toml ./
RUN pip install --no-cache-dir -e "."

# ── Node dependencies ──────────────────────────────────────────────────────────
COPY remotion/package.json remotion/package-lock.json ./remotion/
RUN cd remotion && npm ci --omit=dev

# ── Application source ─────────────────────────────────────────────────────────
COPY remotion/ ./remotion/
COPY agents/ ./agents/
COPY tools/ ./tools/
COPY graph/ ./graph/
COPY state/ ./state/
COPY config/ ./config/

# Ensure output and log directories exist inside the image
RUN mkdir -p outputs logs

# ── Runtime ────────────────────────────────────────────────────────────────────
CMD ["python", "-m", "agents.scheduler"]
