# Base: 공통 환경 설정
FROM node:22-alpine AS base
WORKDIR /app
RUN apk add --no-cache libc6-compat

# Deps: 의존성 설치 (캐싱 효율을 위해 분리)
FROM base AS deps
# 패키지 매니저 파일 복사
COPY frontend/package.json frontend/package-lock.json* frontend/yarn.lock* frontend/pnpm-lock.yaml* ./

# 의존성 설치
RUN \
  if [ -f yarn.lock ]; then yarn --frozen-lockfile; \
  elif [ -f package-lock.json ]; then npm ci; \
  elif [ -f pnpm-lock.yaml ]; then corepack enable pnpm && pnpm i --frozen-lockfile; \
  else echo "Lockfile not found." && exit 1; \
  fi

# ----------------------------------------------------
# Dev: 개발 환경 (docker-compose override용)
# ----------------------------------------------------
FROM base AS dev
WORKDIR /app
# Deps 단계에서 설치한 node_modules를 가져옴
COPY --from=deps /app/node_modules ./node_modules
COPY frontend/ .

ENV NODE_ENV=development
# Next.js 개발 서버 실행
CMD ["npm", "run", "dev"]

# ----------------------------------------------------
# Builder: 프로덕션 빌드 단계
# ----------------------------------------------------
FROM base AS builder
WORKDIR /app
COPY --from=deps /app/node_modules ./node_modules
COPY frontend/ .

# 빌드 실행
RUN \
  if [ -f yarn.lock ]; then yarn build; \
  elif [ -f package-lock.json ]; then npm run build; \
  elif [ -f pnpm-lock.yaml ]; then corepack enable pnpm && pnpm run build; \
  else echo "Lockfile not found." && exit 1; \
  fi

# ----------------------------------------------------
# Runner: 프로덕션 실행 단계 (최적화 이미지)
# ----------------------------------------------------
FROM base AS runner
WORKDIR /app

ENV NODE_ENV=production
ENV NEXT_TELEMETRY_DISABLED 1

RUN addgroup --system --gid 1001 nodejs
RUN adduser --system --uid 1001 nextjs

# 정적 파일 및 Standalone 빌드 결과물 복사
COPY --from=builder /app/public ./public
COPY --from=builder --chown=nextjs:nodejs /app/.next/static ./.next/static
COPY --from=builder --chown=nextjs:nodejs /app/.next/standalone ./

USER nextjs

ENV PORT 3000
ENV HOSTNAME "0.0.0.0"

CMD ["node", "server.js"]