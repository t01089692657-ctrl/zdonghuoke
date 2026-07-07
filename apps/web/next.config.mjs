/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  // antd v5 使用 @ant-design/nextjs-registry 做 SSR 样式抽取，无需 transpilePackages。
  // 关闭遥测，保持构建干净。
  eslint: {
    // 骨架阶段不因 lint 阻断构建；CI 里单独跑 `pnpm lint`。
    ignoreDuringBuilds: true,
  },
};

export default nextConfig;
