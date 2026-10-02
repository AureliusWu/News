<script setup lang="ts">
import {computed, onBeforeUnmount, onMounted, ref, watch} from "vue";
import {useRoute} from "vue-router";
import {getEvents, resolveEventId} from "../api/events";
import type {EventIndex} from "../types/events";
import type {Snapshot} from "../snapshot/transport";
import {formatDateTime} from "../utils/time";
import NewsCard from "../components/NewsCard.vue";
import {readingLibrary} from "../reading/library";
import {filtersFromQuery, queryFromFilters} from "../reading/filterLocation";
import "../reading/reading.css";
import {buildTrends, qualityGate} from "../events/trends";
const route = useRoute();
const returnTo = computed(() => ({name: "home", query: queryFromFilters(filtersFromQuery(route.query))}));
const index = ref<EventIndex | null>(null);
const snapshot = ref<Snapshot | null>(null);
const error = ref("");
const loading = ref(false);
const multipleOnly = ref(false);
const query = ref("");
const order = ref("latest");
const shown = ref(30);
const controller = new AbortController();
const selected = computed(() => index.value?.events.find(e => e.event_id === resolveEventId(index.value!, String(route.params.eventId || ""))));
const timeline = computed(() => snapshot.value?.articles.filter(a => selected.value?.article_ids.includes((a as typeof a & {article_id?: string}).article_id || "")).sort((a, b) => Date.parse(a.published_at) - Date.parse(b.published_at)) || []);
const trends = computed(() => {
  if (!index.value || !snapshot.value) return {report: null, error: ""};
  try { return {report: buildTrends(index.value, snapshot.value), error: ""}; }
  catch { return {report: null, error: "热度规则暂不可用，已保留最新事件和原文。"}; }
});
const trendById = computed(() => new Map(trends.value.report?.events.map(e => [e.event_id, e]) || []));
const selectedTrend = computed(() => selected.value ? trendById.value.get(selected.value.event_id) : undefined);
const aiAccepted = computed(() => index.value?.matcher_version === qualityGate.matcher_version
  && index.value?.acceptance_status === qualityGate.acceptance_status);
const filtered = computed(() => {
  const events = (index.value?.events || []).filter(e => (!multipleOnly.value || e.publisher_count > 1)
    && e.title.toLocaleLowerCase().includes(query.value.trim().toLocaleLowerCase()));
  const chosen = order.value === "hot" && trends.value.report ? events.filter(e => trendById.value.get(e.event_id)?.hot_eligible) : events;
  return chosen.sort((a, b) => {
    if (order.value === "hot" && trends.value.report) {
      const x = trendById.value.get(a.event_id)!, y = trendById.value.get(b.event_id)!;
      const promoted = Number(!!y.pin) - Number(!!x.pin) || (y.pin?.priority ?? 0) - (x.pin?.priority ?? 0);
      if (promoted) return promoted;
      if (x.score !== y.score) return (y.score ?? -1) - (x.score ?? -1);
    }
    if (order.value === "publishers" && a.publisher_count !== b.publisher_count) return b.publisher_count - a.publisher_count;
    return Date.parse(b.last_published_at) - Date.parse(a.last_published_at) || a.event_id.localeCompare(b.event_id);
  });
});
watch([query, multipleOnly, order], () => { shown.value = 30; });
watch(() => readingLibrary.state.font, font => { document.documentElement.dataset.readingFont = font; }, {immediate: true});
async function load() {
  if (loading.value) return;
  loading.value = true; error.value = "";
  try { const result = await getEvents(controller.signal); index.value = result.index; snapshot.value = result.snapshot; }
  catch (e) { if (!controller.signal.aborted) error.value = e instanceof Error ? e.message : "事件暂时无法加载。"; }
  finally { loading.value = false; }
}
onMounted(load); onBeforeUnmount(() => controller.abort());
</script>

<template>
  <section class="reading-page" aria-labelledby="events-title">
    <RouterLink :to="returnTo">返回新闻</RouterLink>
    <h1 id="events-title">{{ route.params.eventId ? '事件报道' : '事件聚合' }}</h1>
    <p>事件聚合预览：依据同语种标题相似度和发布时间保守归组，可能漏合并或误合并。不同语种暂分开呈现；报道数量不代表事实可信度。</p>
    <p v-if="index">快照时间：{{ formatDateTime(index.generated_at) }}</p>
    <p v-if="aiAccepted" class="evaluation-note">AI 评估出口已采用：240 对中 238 对可计分，样本精确率 100%、召回率 50%。仅 15 对预测为同一事件；样本已用于调参，不是独立人工金标，也不代表全部新闻的准确率。</p>
    <p v-else-if="index" class="evaluation-note">当前聚合版本尚未匹配已批准的 AI 评估出口。</p>
    <details v-if="trends.report" class="trend-method">
      <summary>热度怎么算？</summary>
      <p>以快照时间为基准：最近 6 小时相对前 6 小时的报道增长占 40 分、最近发布机构多样性占 40 分、原文新鲜度占 20 分。同机构每个时间窗最多计 2 篇，同机构同链接去重。热度衡量报道活动，不代表事实可信度或机构独立性。</p>
      <p>推荐和排除规则必须注明来源、理由、引用和失效时间；默认没有人工置顶。排除只影响热度视图，不删除新闻或原文。</p>
    </details>
    <p v-if="trends.error" role="status">{{ trends.error }}</p>
    <p v-if="trends.report && !trends.report.promotions_enabled" role="status">数据时间异常或已超过 2 小时，暂停规则推荐；热度仍是快照时点的历史值。</p>
    <p v-if="loading" role="status">正在加载事件报道。</p>
    <p v-if="error" role="alert">{{ error }} <button type="button" @click="load">重试</button></p>
    <template v-if="index && route.params.eventId">
      <RouterLink :to="{name:'events',query:route.query}">返回事件列表</RouterLink>
      <template v-if="selected">
        <p v-if="selected.event_id !== route.params.eventId">该历史事件链接已合并到以下报道，旧链接仍可使用。</p>
        <h2 :lang="selected.language">{{ selected.title }}</h2>
        <p>{{ selected.article_count }} 篇报道 · {{ selected.publisher_count }} 个发布机构。同机构不同订阅源只计一次；不同机构转载同稿的独立性尚未确认。</p>
        <p>最早原文：{{ formatDateTime(selected.first_published_at) }} · 最近原文：{{ formatDateTime(selected.last_published_at) }}</p>
        <p v-if="selectedTrend">快照热度：{{ selectedTrend.score ?? '暂不可计分' }}<span v-if="selectedTrend.score !== null"> / 100。增长 {{ selectedTrend.components.activity }} · 机构多样性 {{ selectedTrend.components.diversity }} · 新鲜度 {{ selectedTrend.components.recency }}</span></p>
        <p v-if="selectedTrend?.pin">{{ selectedTrend.pin.origin === 'ai-reviewed' ? 'AI 审阅规则推荐' : '维护者规则推荐' }}：{{ selectedTrend.pin.reason }}；引用：{{ selectedTrend.pin.reference }}；失效：{{ formatDateTime(selectedTrend.pin.expires_at) }}</p>
        <p v-if="selectedTrend?.exclusion">已从热度视图排除：{{ selectedTrend.exclusion.reason }}；原文仍可阅读。</p>
        <h2>报道时间线</h2>
        <div class="news-list"><NewsCard v-for="article in timeline" :key="article.id" :article="article" /></div>
      </template>
      <p v-else>当前快照中没有该事件的近期报道。事件链接可能已超出数据保留期。</p>
    </template>
    <template v-else-if="index">
      <div class="reading-row"><input v-model="query" type="search" aria-label="搜索事件" placeholder="搜索事件标题" maxlength="200"><label><input v-model="multipleOnly" type="checkbox"> 仅看多机构报道</label></div>
      <label class="event-order">事件排序 <select v-model="order" aria-label="事件排序"><option value="latest">最新原文</option><option value="hot">可解释热度</option><option value="publishers">发布机构数量</option></select></label>
      <p>{{ filtered.length }} 个事件</p>
      <article v-for="event in filtered.slice(0,shown)" :key="event.event_id" class="reading-bookmark">
        <h2 :lang="event.language"><RouterLink :to="{name:'event-detail',params:{eventId:event.event_id},query:route.query}">{{ event.title }}</RouterLink></h2>
        <p>{{ event.article_count }} 篇报道 · {{ event.publisher_count }} 个发布机构 · {{ formatDateTime(event.last_published_at) }}</p>
        <p>{{ event.source_names.join('、') }}</p>
        <p v-if="order === 'hot' && trendById.get(event.event_id)" class="heat-evidence">快照热度 {{ trendById.get(event.event_id)!.score ?? '暂不可计分' }} / 100 · 最近 6 小时 {{ trendById.get(event.event_id)!.counts.recent_reports }} 篇报道 / {{ trendById.get(event.event_id)!.counts.recent_publishers }} 个机构</p>
        <p v-if="order === 'hot' && trendById.get(event.event_id)?.pin">规则推荐：{{ trendById.get(event.event_id)!.pin!.reason }}；引用：{{ trendById.get(event.event_id)!.pin!.reference }}；失效：{{ formatDateTime(trendById.get(event.event_id)!.pin!.expires_at) }}</p>
      </article>
      <button v-if="shown < filtered.length" type="button" @click="shown += 30">加载更多事件</button>
      <p v-if="!filtered.length">没有符合条件的事件，可调整搜索条件。</p>
    </template>
  </section>
</template>

<style scoped>
.evaluation-note, .trend-method { padding: .8rem 1rem; border-inline-start: 3px solid currentColor; background: color-mix(in srgb, currentColor 4%, transparent); }
.trend-method summary { cursor: pointer; font-weight: 600; }
.event-order { display: flex; align-items: center; flex-wrap: wrap; gap: .75rem; margin-block: 1rem; }
.event-order select { font: inherit; color: inherit; background: transparent; padding: .5rem; border: 1px solid currentColor; border-radius: .25rem; }
.heat-evidence { font-variant-numeric: tabular-nums; }
</style>
