# Base: 공통 환경 설정
FROM node:22-alpine AS base
WORKDIR /app
# sharp 등 네이티브 모듈을 위한 호환성 라이브러리
RUN apk add --no-cache libc6-compat

# Deps: 의존성 설치 (캐시 마운트 적용)
FROM base AS deps
COPY frontend/package.json frontend/package-lock.json* frontend/yarn.lock* frontend/pnpm-lock.yaml* ./

# [최적화] --mount=type=cache를 사용하여 패키지 다운로드 속도 최적화
RUN --mount=type=cache,target=/root/.npm \
  if [ -f yarn.lock ]; then yarn --frozen-lockfile; \
  elif [ -f package-lock.json ]; then npm ci --cache /root/.npm; \
  elif [ -f pnpm-lock.yaml ]; then corepack enable pnpm && pnpm i --frozen-lockfile; \
  else echo "Lockfile not found." && exit 1; \
  fi

# Dev: 개발 환경
FROM base AS dev
COPY --from=deps /app/node_modules ./node_modules
COPY frontend/ .
ENV NODE_ENV=development
CMD ["npm", "run", "dev"]

# Builder: 프로덕션 빌드 단계
FROM base AS builder
WORKDIR /app
COPY --from=deps /app/node_modules ./node_modules
COPY frontend/ .
ENV NEXT_TELEMETRY_DISABLED 1

# 빌드 실행
RUN \
  if [ -f yarn.lock ]; then yarn build; \
  elif [ -f package-lock.json ]; then npm run build; \
  elif [ -f pnpm-lock.yaml ]; then corepack enable pnpm && pnpm run build; \
  else echo "Lockfile not found." && exit 1; \
  fi

# Runner: 프로덕션 실행 단계
FROM base AS runner
WORKDIR /app

ENV NODE_ENV=production
ENV NEXT_TELEMETRY_DISABLED 1

RUN addgroup --system --gid 1001 nodejs
RUN adduser --system --uid 1001 nextjs

# [최적화] standalone 결과물만 복사 (이미지 용량 최소화)
COPY --from=builder /app/public ./public
COPY --from=builder --chown=nextjs:nodejs /app/.next/static ./.next/static
COPY --from=builder --chown=nextjs:nodejs /app/.next/standalone ./

USER nextjs

EXPOSE 3000
ENV PORT 3000
ENV HOSTNAME "0.0.0.0"

CMD ["node", "server.js"]