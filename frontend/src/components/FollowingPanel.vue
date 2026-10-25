<script setup lang="ts">
import {computed, onBeforeUnmount, onMounted, ref} from 'vue';
import {continuity, MAX_CONTINUITY_BYTES} from '../reading/continuity';
import {queryFromFilters} from '../reading/filterLocation';
import {getEvents} from '../api/events';
import type {EventIndex, NewsEvent} from '../types/events';
const index = ref<EventIndex | null>(null); const message = ref(''); const loading = ref(false);
const controller = new AbortController();
const rows = computed(() => continuity.state.follows.map(follow => ({follow, event: index.value?.events.find(item => item.event_id === follow.event_id)})));
async function refresh() {
  if (loading.value || !continuity.state.follows.length) return;
  loading.value = true;
  try { const result = await getEvents(controller.signal); continuity.synchronize(result.index); index.value = result.index; message.value = ''; }
  catch { if (!controller.signal.aborted) message.value = '暂时无法检查新增报道，关注记录仍保留，可稍后重试。'; }
  finally { loading.value = false; }
}
function seen(event: NewsEvent) { try { continuity.markSeen(event); } catch(e) { message.value = e instanceof Error ? e.message : '更新失败。'; } }
function exportFile() {
  const url = URL.createObjectURL(new Blob([continuity.exportBackup()], {type:'application/json'}));
  const link = document.createElement('a'); link.href = url; link.download = `news-following-${new Date().toISOString().slice(0,10)}.json`; link.click();
  window.setTimeout(() => URL.revokeObjectURL(url), 1000);
  message.value = '已生成关注与筛选备份，请确认下载完成。新闻收藏仍使用上方的独立备份。';
}
async function importFile(event: Event) {
  const input = event.target as HTMLInputElement; const file = input.files?.[0]; if (!file) return;
  try {
    if (file.size > MAX_CONTINUITY_BYTES) throw new Error('备份超过 2 MB，未导入。');
    continuity.importBackup(await file.text()); message.value = continuity.state.warning || '关注与筛选已合并，已有方案未覆盖。';
  } catch(e) { message.value = e instanceof Error ? e.message : '导入失败，原记录未更改。'; }
  finally { input.value = ''; }
}
onMounted(refresh); onBeforeUnmount(() => controller.abort());
</script>
<template>
  <section class="following-panel" aria-labelledby="following-title">
    <h2 id="following-title">关注的事件</h2>
    <p>新增指当前快照中尚未标为已阅的报道，不代表事实已被确认。没有近期报道的事件仍保留关注。</p>
    <button type="button" :disabled="loading || !rows.length" @click="refresh">{{ loading ? '正在检查' : '检查新增报道' }}</button>
    <p v-if="!rows.length">还没有关注事件，可在事件详情或列表中选择“关注事件”。</p>
    <article v-for="row in rows" :key="row.follow.event_id" class="following-card">
      <h3><RouterLink :to="{name:'event-detail',params:{eventId:row.follow.event_id}}">{{ row.event?.title ?? row.follow.title }}</RouterLink></h3>
      <p v-if="row.event">新增收录 {{ continuity.newCount(row.event) }} 篇 · 当前 {{ row.event.article_count }} 篇报道</p>
      <p v-else>{{ index ? '当前快照暂无报道' : '尚未取得最新报道，请联网检查' }}</p>
      <div class="reading-row"><button v-if="row.event" type="button" @click="seen(row.event)">将当前报道标为已阅</button><button type="button" @click="continuity.removeFollow(row.follow.event_id)">取消关注</button></div>
    </article>
    <h2>已存筛选方案</h2>
    <p v-if="!continuity.state.views.length">在首页阅读工具中展开“我的筛选方案”，即可保存常用组合。</p>
    <ul><li v-for="view in continuity.state.views" :key="view.id"><RouterLink :to="{name:'home',query:queryFromFilters(view.filters)}">{{ view.name }}</RouterLink></li></ul>
    <details><summary>关注与筛选备份</summary><p>此备份不包含新闻收藏、已读记录或全文，且不会上传到服务器。</p><div class="reading-row"><button type="button" @click="exportFile">导出关注与筛选</button><label class="reading-import">导入关注与筛选 <input type="file" accept="application/json,.json" aria-label="导入关注与筛选" @change="importFile"></label></div></details>
    <p v-if="message" role="status">{{ message }}</p><p v-if="continuity.state.warning" role="alert">{{ continuity.state.warning }}</p>
  </section>
</template>
