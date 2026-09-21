<script setup lang="ts">
import {computed, onBeforeUnmount, onMounted, ref} from "vue";
import NewsCard from "../components/NewsCard.vue";
import {useNews} from "../composables/useNews";
import {getMeta, getSources} from "../api/client";
import type {NewsMeta, NewsSource} from "../types/news";

const {filters, items, loading, error, hasMore, stale, load, retry} = useNews();
const meta = ref<NewsMeta | null>(null);
const sources = ref<NewsSource[]>([]);
const query = ref("");
const offline = ref(!navigator.onLine);
const now = ref(Date.now());
const sentinel = ref<HTMLElement | null>(null);
const tabs = [
  {label: "Latest", region: "", category: ""},
  ...["World", "China", "US", "Japan", "Europe", "Asia"].map(label => ({label, region: label.toLowerCase(), category: ""})),
  ...["Business", "Technology", "Science"].map(label => ({label, region: "", category: label.toLowerCase()}))
];
const selectedTab = computed(() => tabs.find(t => t.region === filters.region && t.category === filters.category)?.label || "Filtered news");
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
  <section class="timeline" aria-label="News timeline">
    <div class="timeline-heading">
      <div><p class="eyebrow">Across borders. From the source.</p><h1>Latest news</h1></div>
      <button class="refresh-button" :disabled="loading" @click="load('refresh')">{{ loading && items.length ? "Updating..." : "Refresh" }}</button>
    </div>
    <nav class="topic-tabs" aria-label="News sections">
      <button v-for="tab in tabs" :key="tab.label" :aria-pressed="selectedTab === tab.label" @click="pickTab(tab)">{{ tab.label }}</button>
    </nav>
    <div class="filter-bar">
      <form class="search-form" role="search" @submit.prevent="filters.q = query.trim()">
        <input v-model="query" type="search" placeholder="Search headlines" aria-label="Search headlines" maxlength="200" />
        <button type="submit">Search</button>
      </form>
      <details class="filters">
        <summary>Filter news</summary>
        <div class="filter-options">
          <label>Region<select v-model="filters.region"><option value="">All regions</option><option v-for="region in allRegions" :key="region" :value="region">{{ region }}</option></select></label>
          <label>Language<select v-model="filters.language"><option value="">All languages</option><option v-for="language in meta?.languages || []" :key="language" :value="language">{{ language }}</option></select></label>
          <label>Source<select v-model="filters.source"><option value="">All sources</option><option v-for="source in sources" :key="source.id" :value="source.slug">{{ source.name }}</option></select></label>
        </div>
      </details>
    </div>
    <p v-if="offline || stale" class="status-notice" role="status">{{ offline ? "You are offline." : "Showing cached news." }} These stories may be out of date. Reconnect or refresh for the latest.</p>
    <div v-if="loading && !items.length" class="skeleton-list" role="status" aria-label="Loading news">
      <div v-for="i in 5" :key="i" class="skeleton-card"><div class="skeleton short"></div><div class="skeleton title"></div><div class="skeleton"></div></div>
    </div>
    <div v-if="items.length" class="news-list" aria-label="Articles">
      <NewsCard v-for="item in items" :key="item.id" :article="item" :now="now" />
    </div>
    <div v-if="error" class="empty-state" role="alert">
      <h2>We couldn't load the news</h2><p>{{ error }}</p><button @click="retry">Try again</button>
    </div>
    <div v-else-if="!loading && !items.length" class="empty-state">
      <h2>{{ meta?.article_count === 0 ? "The first stories are on their way" : "No stories found" }}</h2>
      <p>{{ meta?.article_count === 0 ? "We're collecting the latest news. This page will update automatically." : "Try another section or change your search." }}</p>
      <button @click="load('refresh')">Refresh news</button>
    </div>
    <div ref="sentinel" class="load-more">
      <p v-if="loading && items.length" role="status">Loading stories...</p>
      <button v-else-if="hasMore && !error" @click="load('more')">Load more stories</button>
      <p v-else-if="items.length && !error">You're all caught up.</p>
    </div>
  </section>
</template>