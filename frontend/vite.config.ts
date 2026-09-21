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
        name: "Global News", short_name: "Global News",
        description: "Recent reporting from publishers around the world.",
        theme_color: "#143443", background_color: "#f4f8fb",
        display: "standalone", start_url: basePath, scope: basePath,
        icons: [
          {src: basePath + "icons/icon-192.png", sizes: "192x192", type: "image/png", purpose: "any"},
          {src: basePath + "icons/icon-512.png", sizes: "512x512", type: "image/png", purpose: "any"}
        ]
      },
      workbox: {
        navigateFallback: basePath + "index.html",
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