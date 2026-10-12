FROM node:22-alpine

WORKDIR /app

# 依赖层单独缓存（ali-oss 是 optional，装不上也不阻断 local 驱动）
COPY package.json ./
RUN npm install --omit=dev --no-audit --no-fund || true

COPY index.js storage.js ./

ENV NODE_ENV=production \
    PORT=9000 \
    HOST=0.0.0.0 \
    STATE_DIR=/data/mcp-state \
    STORAGE_DRIVER=local

RUN mkdir -p /data && chown -R node:node /data
USER node

EXPOSE 9000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD node -e "fetch('http://127.0.0.1:'+(process.env.PORT||9000)+'/healthz').then(r=>process.exit(r.ok?0:1)).catch(()=>process.exit(1))"

CMD ["node", "index.js"]
