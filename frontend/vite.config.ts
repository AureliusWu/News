import {defineConfig} from "vite";
import vue from "@vitejs/plugin-vue";
import {VitePWA} from "vite-plugin-pwa";

export default defineConfig({
  plugins: [
    vue(),
    VitePWA({
      registerType: "autoUpdate",
      includeAssets: ["favicon.ico", "favicon.svg", "robots.txt", "placeholder.html"],
      manifest: {
        name: "Global News",
        short_name: "Global News",
        description: "A global news aggregator skeleton PWA.",
        theme_color: "#0b1220",
        background_color: "#f7fafc",
        display: "standalone",
        start_url: "/",
        scope: "/",
        icons: [
          {
            src: "/icons/icon-192.png",
            sizes: "192x192",
            type: "image/png",
            purpose: "any"
          },
          {
            src: "/icons/icon-512.png",
            sizes: "512x512",
            type: "image/png",
            purpose: "any"
          }
        ]
      },
      workbox: {
        navigateFallback: "/index.html",
        runtimeCaching: [
          {
            urlPattern: /^https:\/\/.*\/api\/v1\/.+$/i,
            handler: "NetworkFirst",
            options: {
              cacheName: "global-news-api",
              expiration: {
                maxEntries: 50,
                maxAgeSeconds: 60 * 60
              }
            }
          },
          {
            urlPattern: /\.(?:png|jpg|jpeg|svg|webp)$/,
            handler: "CacheFirst",
            options: {
              cacheName: "global-news-images",
              expiration: {
                maxEntries: 100,
                maxAgeSeconds: 24 * 60 * 60
              }
            }
          }
        ]
      }
    })
  ],
  resolve: {
    alias: {
      "@": "/src"
    }
  },
  test: {
    environment: "jsdom",
    globals: true,
    include: ["./src/**/*.{test,spec}.{js,ts}"]
  }
});
