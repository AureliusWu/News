import {onBeforeUnmount, reactive, ref, watch} from "vue";
import {getNews} from "../api/client";
import type {NewsArticle, NewsFilters} from "../types/news";

export function useNews() {
  const filters = reactive<NewsFilters>({region: "", category: "", language: "", source: "", q: ""});
  const items = ref<NewsArticle[]>([]);
  const loading = ref(false);
  const error = ref("");
  const hasMore = ref(false);
  const nextCursor = ref<string | null>(null);
  const stale = ref(false);
  let generation = 0;
  let controller: AbortController | undefined;
  let failedMode: "reset" | "refresh" | "more" = "reset";

  async function load(mode: "reset" | "refresh" | "more" = "refresh") {
    if (mode !== "reset" && loading.value) return;
    if (mode === "more" && (!hasMore.value || !nextCursor.value)) return;
    controller?.abort();
    controller = new AbortController();
    const current = ++generation;
    if (mode === "reset") {
      items.value = [];
      nextCursor.value = null;
      hasMore.value = false;
    }
    loading.value = true;
    error.value = "";
    failedMode = mode;
    try {
      const result = await getNews({...filters}, mode === "more" ? nextCursor.value : null, controller.signal);
      if (current !== generation) return;
      const incoming = mode === "more" ? [...items.value, ...result.page.items] : result.page.items;
      items.value = [...new Map(incoming.map(item => [item.id, item])).values()];
      nextCursor.value = result.page.next_cursor;
      hasMore.value = result.page.has_more;
      stale.value = result.stale;
    } catch {
      if (current === generation) error.value = "News could not be loaded. Please try again.";
    } finally {
      if (current === generation) loading.value = false;
    }
  }
  watch(() => JSON.stringify(filters), () => load("reset"));
  onBeforeUnmount(() => { generation++; controller?.abort(); });
  return {filters, items, loading, error, hasMore, stale, load, retry: () => load(failedMode)};
}