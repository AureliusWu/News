<script setup lang="ts">
import {computed, onBeforeUnmount, onMounted, ref} from "vue";
import NewsCard from "../components/NewsCard.vue";
import {useNews} from "../composables/useNews";
import {getMeta, getSources} from "../api/client";
import type {NewsMeta, NewsSource} from "../types/news";
import {ui, categoryLabel, languageLabel, regionLabel} from "../locales/zh-CN";

const {filters, items, loading, error, hasMore, stale, load, retry} = useNews();
const meta = ref<NewsMeta | null>(null);
const sources = ref<NewsSource[]>([]);
const query = ref("");
const offline = ref(!navigator.onLine);
const now = ref(Date.now());
const sentinel = ref<HTMLElement | null>(null);
const tabs = [
  {label: ui.home.latest, region: "", category: ""},
  ...["world", "china", "us", "japan", "europe", "asia"].map(region => ({label: regionLabel(region), region, category: ""})),
  ...["business", "technology", "science"].map(category => ({label: categoryLabel(category), region: "", category}))
];
const selectedTab = computed(() => tabs.find(t => t.region === filters.region && t.category === filters.category)?.label || ui.home.filtered);
const allRegions = computed(() => meta.value?.regions || ["world", "china", "us", "japan", "europe", "asia", "middle-east", "africa", "oceania", "americas"]);
let observer: IntersectionObserver | undefined;
let timer: ReturnType<typeof setInterval> | undefined;

function updateConnection() {
  offline.value = !navigator.onLine;
  if (!offline.value) void load("refresh");
}
function refreshOnFocus() { if (!document.hidden && !offline.value) void load("refresh"); }
function pickTab(tab: typeof tabs[number]) {
  filters.region = tab.region;
  filters.category = tab.category;
}
onMounted(() => {
  void load("reset");
  void getMeta().then(data => { meta.value = data; }).catch(() => {});
  void getSources().then(data => { sources.value = data; }).catch(() => {});
  if (typeof IntersectionObserver !== "undefined") {
    observer = new IntersectionObserver(entries => {
      if (entries.some(entry => entry.isIntersecting) && items.value.length && !error.value) void load("more");
    }, {rootMargin: "400px"});
    if (sentinel.value) observer.observe(sentinel.value);
  }
  window.addEventListener("online", updateConnection);
  window.addEventListener("offline", updateConnection);
  document.addEventListener("visibilitychange", refreshOnFocus);
  timer = setInterval(() => {
    now.value = Date.now();
    if (!document.hidden && !offline.value && (items.value.length === 0 || window.scrollY < 100)) void load("refresh");
  }, 60000);
});
onBeforeUnmount(() => {
  observer?.disconnect();
  if (timer) clearInterval(timer);
  window.removeEventListener("online", updateConnection);
  window.removeEventListener("offline", updateConnection);
  document.removeEventListener("visibilitychange", refreshOnFocus);
});
</script>

<template>
  <section class="timeline" :aria-label="ui.home.timeline">
    <div class="timeline-heading">
      <div><p class="eyebrow">{{ ui.home.eyebrow }}</p><h1>{{ ui.home.title }}</h1></div>
      <button class="refresh-button" :disabled="loading" @click="load('refresh')">{{ loading && items.length ? ui.home.updating : ui.home.refresh }}</button>
    </div>
    <nav class="topic-tabs" :aria-label="ui.home.sections">
      <button v-for="tab in tabs" :key="tab.label" :aria-pressed="selectedTab === tab.label" @click="pickTab(tab)">{{ tab.label }}</button>
    </nav>
    <div class="filter-bar">
      <form class="search-form" role="search" @submit.prevent="filters.q = query.trim()">
        <input v-model="query" type="search" :placeholder="ui.home.searchPlaceholder" :aria-label="ui.home.searchPlaceholder" maxlength="200" />
        <button type="submit">{{ ui.home.search }}</button>
      </form>
      <details class="filters">
        <summary>{{ ui.home.filters }}</summary>
        <div class="filter-options">
          <label>{{ ui.home.region }}<select v-model="filters.region"><option value="">{{ ui.home.allRegions }}</option><option v-for="region in allRegions" :key="region" :value="region">{{ regionLabel(region) }}</option></select></label>
          <label>{{ ui.home.language }}<select v-model="filters.language"><option value="">{{ ui.home.allLanguages }}</option><option v-for="language in meta?.languages || []" :key="language" :value="language">{{ languageLabel(language) }}</option></select></label>
          <label>{{ ui.home.source }}<select v-model="filters.source"><option value="">{{ ui.home.allSources }}</option><option v-for="source in sources" :key="source.id" :value="source.slug">{{ source.name }}</option></select></label>
        </div>
      </details>
    </div>
    <p v-if="offline || stale" class="status-notice" role="status">{{ offline ? ui.home.offline : ui.home.cached }} {{ ui.home.staleHint }}</p>
    <div v-if="loading && !items.length" class="skeleton-list" role="status" :aria-label="ui.home.loading">
      <div v-for="i in 5" :key="i" class="skeleton-card"><div class="skeleton short"></div><div class="skeleton title"></div><div class="skeleton"></div></div>
    </div>
    <div v-if="items.length" class="news-list" :aria-label="ui.home.articles">
      <NewsCard v-for="item in items" :key="item.id" :article="item" :now="now" />
    </div>
    <div v-if="error" class="empty-state" role="alert">
      <h2>{{ ui.home.loadFailed }}</h2><p>{{ error }}</p><button @click="retry">{{ ui.home.retry }}</button>
    </div>
    <div v-else-if="!loading && !items.length" class="empty-state">
      <h2>{{ meta?.article_count === 0 ? ui.home.firstStories : ui.home.noStories }}</h2>
      <p>{{ meta?.article_count === 0 ? ui.home.collecting : ui.home.changeFilters }}</p>
      <button @click="load('refresh')">{{ ui.home.refreshNews }}</button>
    </div>
    <div ref="sentinel" class="load-more">
      <p v-if="loading && items.length" role="status">{{ ui.home.loadingMore }}</p>
      <button v-else-if="hasMore && !error" @click="load('more')">{{ ui.home.loadMore }}</button>
      <p v-else-if="items.length && !error">{{ ui.home.caughtUp }}</p>
    </div>
  </section>
</template>
