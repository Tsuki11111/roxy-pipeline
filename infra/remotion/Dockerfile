# Pinned Remotion sandbox. Build from the repository root:
#   docker build -f infra/remotion/Dockerfile -t roxy-remotion:4.0.539 .
FROM node:22-bookworm-slim

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
       libnss3 libnspr4 libatk1.0-0 libatk-bridge2.0-0 libcups2 libdrm2 \
       libxkbcommon0 libxcomposite1 libxdamage1 libxfixes3 libxrandr2 \
       libgbm1 libasound2 fonts-noto-cjk \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY app/agents/remotion/templates/package.json app/agents/remotion/templates/package-lock.json ./
RUN npm ci --ignore-scripts --no-audit --no-fund
COPY app/agents/remotion/templates/ ./

RUN useradd -u 10001 -m appuser \
    && mkdir -p /home/appuser/.cache \
    && chown -R appuser:appuser /app /home/appuser
USER appuser
ENV TMPDIR=/tmp
RUN npx --no-install remotion browser ensure

CMD ["node", "/app/scripts/validate.mjs"]
