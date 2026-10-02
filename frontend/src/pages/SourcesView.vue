<script setup lang="ts">
import {computed, onBeforeUnmount, onMounted, ref} from "vue";
import {useRoute} from "vue-router";
import {filtersFromQuery, queryFromFilters} from "../reading/filterLocation";
import {parseHealthReport, healthDescription, type HealthReport} from "../reading/sourceHealth";
import {formatDateTime} from "../utils/time";
import "../reading/reading.css";
import {getProvider} from "../api/providers";

const report = ref<HealthReport | null>(null);
const error = ref("");
const loading = ref(false);
const failuresOnly = ref(false);
const snapshotMode = import.meta.env.VITE_NEWS_MODE === "snapshot";
const route = useRoute();
const returnTo = computed(() => ({name: "home", query: queryFromFilters(filtersFromQuery(route.query))}));
const visible = computed(() => (report.value?.sources || []).filter(s => !failuresOnly.value || s.health !== "PASS"));
const healthy = computed(() => report.value?.sources.filter(s => s.health === "PASS").length ?? 0);
const controller = new AbortController();
const now = ref(Date.now());
const timer = window.setInterval(() => { now.value = Date.now(); }, 60000);
const age = computed(() => report.value ? (now.value - Date.parse(report.value.checked_at)) / 3600000 : null);
async function load() {
  if (loading.value || !snapshotMode) return;
  loading.value = true; error.value = "";
  try {
    const provider = getProvider();
    const snapshot = await provider.snapshot(controller.signal);
    if (snapshot.source_health_file) {
      report.value = parseHealthReport(await provider.asset(snapshot, snapshot.source_health_file, controller.signal));
      return;
    }
    const url = new URL(`${import.meta.env.BASE_URL}data/source-health.json`, location.origin);
    const response = await fetch(url, {cache: "no-store", signal: AbortSignal.any([controller.signal, AbortSignal.timeout(12000)])});
    if (!response.ok || !response.headers.get("content-type")?.includes("application/json")) throw new Error("来源报告暂不可用。");
    const raw = await response.text();
    if (raw.length > 2 * 1024 * 1024) throw new Error("来源报告超过大小限制。");
    const value = parseHealthReport(JSON.parse(raw));
    if (value.checked_at !== snapshot.generated_at) throw new Error("来源报告与新闻快照版本不同，请稍后重试。");
    report.value = value;
  } catch (e) { if (!controller.signal.aborted) error.value = e instanceof Error ? e.message : "读取来源报告失败，请稍后重试。"; }
  finally { loading.value = false; }
}
onMounted(load);
onBeforeUnmount(() => { controller.abort(); clearInterval(timer); });
</script>

<template>
  <section class="reading-page" aria-labelledby="sources-title">
    <RouterLink :to="returnTo">返回新闻</RouterLink>
    <h1 id="sources-title">来源状态</h1>
    <p>这是已发布快照的采集记录，不是实时连通性检测，也不是媒体可信度评分。多个订阅源可能属于同一发布机构。</p>
    <p v-if="!snapshotMode">当前为 API 模式。此页面仅展示 Pages 快照报告，请通过后端运维工具查看实时采集状态。</p>
    <div v-else class="reading-row"><button type="button" :disabled="loading" @click="load">{{ loading ? '正在读取' : '刷新来源报告' }}</button><label><input v-model="failuresOnly" type="checkbox"> 仅看异常</label></div>
    <p v-if="error" role="alert">{{ error }}{{ report ? ' 下方保留上次读取的报告，并非本次刷新结果。' : '' }}</p>
    <template v-if="report">
      <p>采集时间：<time :datetime="report.checked_at">{{ formatDateTime(report.checked_at) }}</time> · 正常 {{ healthy }} / {{ report.sources.length }}</p>
      <p v-if="age !== null && age > 2" role="status">{{ age > 72 ? '报告已超过 72 小时，仅供历史参考。' : '报告距今超过 2 小时，不能代表当前来源状态。' }}</p>
      <ul class="reading-source-list">
        <li v-for="source in visible" :key="source.id">
          <h2>{{ source.name }}</h2>
          <p>{{ source.publisher }} · {{ healthDescription(source) }} · 合规条目 {{ source.entry_count }}</p>
          <p>最近原文发布时间：{{ source.latest_entry ? formatDateTime(source.latest_entry) : '未知' }}</p>
          <p v-if="source.notes">原始采集说明：{{ source.notes }}</p>
        </li>
      </ul>
      <p v-if="!visible.length">没有符合条件的来源。</p>
    </template>
  </section>
</template>
