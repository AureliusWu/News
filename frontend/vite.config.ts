import {defineConfig} from "vitest/config";
import vue from "@vitejs/plugin-vue";
import {VitePWA} from "vite-plugin-pwa";

const basePath = (process.env.BASE_PATH || "/").replace(/\/?$/, "/");
export default defineConfig({
  base: basePath,
  plugins: [
    vue(),
    VitePWA({
      registerType: "autoUpdate",
      includeAssets: ["favicon.svg", "robots.txt"],
      manifest: {
        name: "全球新闻 | Global News", short_name: "全球新闻", lang: "zh-CN",
        description: "汇集全球媒体报道，保留原文与来源，支持地区、语言和关键词筛选。",
        theme_color: "#143443", background_color: "#f4f8fb",
        display: "standalone", start_url: "./", scope: "./",
        icons: [
          {src: "icons/icon-192.png", sizes: "192x192", type: "image/png", purpose: "any"},
          {src: "icons/icon-512.png", sizes: "512x512", type: "image/png", purpose: "any"}
        ]
      },
      workbox: {
        // Resolve against the service worker URL, including a CLI --base override.
        navigateFallback: "index.html",
        navigateFallbackDenylist: [/\/api\//],
        cleanupOutdatedCaches: true,
        runtimeCaching: [
          {
            urlPattern: ({url}) => /\/api\/v1\/(news|sources|meta)(\/|$)/.test(url.pathname),
            handler: "NetworkFirst",
            options: {
              cacheName: "global-news-api-v020",
              networkTimeoutSeconds: 3,
              cacheableResponse: {statuses: [200]},
              expiration: {maxEntries: 50, maxAgeSeconds: 86400},
              plugins: [{
                cachedResponseWillBeUsed: async ({cachedResponse}) => {
                  if (!cachedResponse) return null;
                  const headers = new Headers(cachedResponse.headers);
                  headers.set("X-News-Cache", "hit");
                  return new Response(cachedResponse.body, {status: cachedResponse.status, statusText: cachedResponse.statusText, headers});
                }
              }]
            }
          },
          {
            urlPattern: ({request}) => request.destination === "image",
            handler: "CacheFirst",
            options: {
              cacheName: "global-news-images-v020",
              cacheableResponse: {statuses: [0, 200]},
              expiration: {maxEntries: 80, maxAgeSeconds: 86400}
            }
          }
        ]
      }
    })
  ],
  resolve: {alias: {"@": "/src"}},
  server: {proxy: {"/api": {target: "http://127.0.0.1:8000", changeOrigin: true}}},
  test: {environment: "jsdom", globals: true, include: ["./src/**/*.{test,spec}.{js,ts}"]}
});
