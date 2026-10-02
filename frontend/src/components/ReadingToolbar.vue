<script setup lang="ts">
import {computed, inject, ref, watch} from "vue";
import {routerKey} from "vue-router";
import type {NewsFilters} from "../types/news";
import {readingLibrary as library, type FontSize} from "../reading/library";
import {FILTER_KEYS, filtersFromQuery, queryFromFilters} from "../reading/filterLocation";
import "../reading/reading.css";
import packageInfo from "../../package.json";

const props = defineProps<{filters: NewsFilters}>();
const router = inject(routerKey, null);
const message = ref("");
const updating = ref(false);
const sharedLink = ref("");
const base = import.meta.env.BASE_URL;
const hasFilters = computed(() => FILTER_KEYS.some(key => Boolean(props.filters[key])));
if (router) {
  Object.assign(props.filters, filtersFromQuery(router.currentRoute.value.query));
  watch(() => router.currentRoute.value.query, query => {
    if (router.currentRoute.value.name === "home") Object.assign(props.filters, filtersFromQuery(query));
  });
  watch(() => JSON.stringify(props.filters), () => {
    if (router.currentRoute.value.name !== "home") return;
    const query = queryFromFilters(props.filters);
    if (JSON.stringify(filtersFromQuery(router.currentRoute.value.query)) !== JSON.stringify(filtersFromQuery(query))) {
      void router.push({name: "home", query}).catch(() => { message.value = "筛选已应用，但地址栏未更新。"; });
    }
  });
}
watch(() => library.state.font, font => { document.documentElement.dataset.readingFont = font; }, {immediate: true});
function clear() { Object.assign(props.filters, filtersFromQuery({})); }
function pageHref(path: string) {
  const query = new URLSearchParams(queryFromFilters(props.filters)).toString();
  return `${base}${path}${query ? `?${query}` : ""}`;
}
function openPage(event: MouseEvent, path: string) {
  if (!router || event.button !== 0 || event.ctrlKey || event.metaKey || event.shiftKey || event.altKey) return;
  event.preventDefault();
  void router.push({path: `/${path}`, query: queryFromFilters(props.filters)});
}
async function share() {
  const url = new URL(base, window.location.origin);
  url.search = new URLSearchParams(queryFromFilters(props.filters)).toString();
  sharedLink.value = url.href;
  try {
    await navigator.clipboard.writeText(url.href);
    message.value = "筛选链接已复制，不包含收藏和已读记录。";
  } catch { message.value = "无法自动复制，可使用下方链接。"; }
}
async function updatePage() {
  updating.value = true;
  message.value = "正在检查页面更新，收藏不会被清除。";
  try {
    if (!("serviceWorker" in navigator)) { window.location.reload(); return; }
    const registration = await navigator.serviceWorker.getRegistration(base);
    if (registration?.scope === new URL(base, location.origin).href) {
      await registration.update();
      const worker = registration.installing || registration.waiting;
      if (worker) {
        const activated = await new Promise<boolean>(resolve => {
          const timeout = window.setTimeout(() => { worker.removeEventListener("statechange", change); resolve(false); }, 15000);
          function change() {
            if (worker!.state === "installed") worker!.postMessage({type: "SKIP_WAITING"});
            if (worker!.state === "activated" || worker!.state === "redundant") {
              clearTimeout(timeout); worker!.removeEventListener("statechange", change);
              resolve(worker!.state === "activated");
            }
          }
          worker.addEventListener("statechange", change); change();
        });
        if (!activated) { message.value = "更新尚未就绪，请保持联网后重试。当前页面仍可阅读。"; return; }
      }
    }
    window.location.reload();
  } catch { message.value = "暂时无法检查更新，请确认网络后重试。现有收藏和缓存未被清除。"; }
  finally { updating.value = false; }
}
</script>

<template>
  <aside class="reading-toolbar" aria-label="阅读工具">
    <div class="reading-row">
      <a :href="pageHref('events')" @click="openPage($event, 'events')">事件聚合</a>
      <a :href="pageHref('library')" @click="openPage($event, 'library')">我的收藏（{{ library.state.bookmarks.length }}）</a>
      <a :href="pageHref('sources')" @click="openPage($event, 'sources')">来源状态</a>
      <button type="button" :disabled="!hasFilters" @click="clear">清除筛选</button>
      <button type="button" @click="share">分享筛选</button>
      <label>阅读字号 <select aria-label="阅读字号" :value="library.state.font" @change="library.setFont(($event.target as HTMLSelectElement).value as FontSize)"><option value="normal">标准</option><option value="large">大</option><option value="larger">特大</option></select></label>
    </div>
    <details>
      <summary>页面更新与本地收藏</summary>
      <p>V{{ packageInfo.version }} · 功能预览</p>
      <p>计划每 30 分钟采集，但免费调度可能延迟数小时；以快照时间为准。收藏仅存于本机浏览器，不会自动跨设备同步。</p>
      <button type="button" :disabled="updating" @click="updatePage">{{ updating ? '正在检查' : '检查页面更新' }}</button>
    </details>
    <p v-if="library.state.warning" role="alert">{{ library.state.warning }}</p>
    <p v-if="message" role="status">{{ message }}</p>
    <p v-if="sharedLink"><a :href="sharedLink">打开当前筛选链接</a></p>
  </aside>
</template>
