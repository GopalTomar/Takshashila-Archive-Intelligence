# Frontend image: Next.js standalone build.
FROM node:22-alpine AS builder
WORKDIR /app
COPY apps/web/package.json apps/web/package-lock.json* ./
RUN npm install --no-audit --no-fund
COPY apps/web ./
ENV NEXT_TELEMETRY_DISABLED=1
RUN npm run build

FROM node:22-alpine AS runner
WORKDIR /app
ENV NODE_ENV=production NEXT_TELEMETRY_DISABLED=1
COPY --from=builder /app/.next/standalone ./
COPY --from=builder /app/.next/static ./.next/static
COPY --from=builder /app/public ./public
EXPOSE 3000
CMD ["node", "server.js"]
