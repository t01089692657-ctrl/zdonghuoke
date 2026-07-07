# syntax=docker/dockerfile:1
# 多阶段构建：deps 安装依赖 → build 产出 .next → runner 用 `next start` 起服务。
# 被根目录 docker-compose.yml 的 web 服务（context: ./apps/web）引用。

FROM node:22-alpine AS base
ENV PNPM_HOME="/pnpm"
ENV PATH="$PNPM_HOME:$PATH"
ENV NEXT_TELEMETRY_DISABLED=1
RUN corepack enable

# ---- 依赖层：单独缓存 node_modules ----
FROM base AS deps
WORKDIR /app
COPY package.json pnpm-lock.yaml* ./
# 有锁文件用 frozen-lockfile；无锁文件（首次）则普通安装
RUN pnpm install --frozen-lockfile || pnpm install

# ---- 构建层 ----
FROM base AS build
WORKDIR /app
COPY --from=deps /app/node_modules ./node_modules
COPY . .
# NEXT_PUBLIC_* 在构建期内联进产物，故这里以 ARG 接收（默认与 compose 一致），
# 需改后端地址时可 `docker build --build-arg NEXT_PUBLIC_API_BASE_URL=...`。
ARG NEXT_PUBLIC_API_BASE_URL=http://localhost:8000
ENV NEXT_PUBLIC_API_BASE_URL=$NEXT_PUBLIC_API_BASE_URL
RUN pnpm build

# ---- 运行层：next start，暴露 3000 ----
FROM base AS runner
WORKDIR /app
ENV NODE_ENV=production
# 后端地址由 docker-compose 注入 NEXT_PUBLIC_API_BASE_URL（构建期与运行期一致时更佳）
COPY --from=build /app/node_modules ./node_modules
COPY --from=build /app/.next ./.next
COPY --from=build /app/public ./public
COPY --from=build /app/package.json ./package.json
COPY --from=build /app/next.config.mjs ./next.config.mjs
EXPOSE 3000
CMD ["pnpm", "start"]
