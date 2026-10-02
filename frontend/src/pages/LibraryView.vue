<script setup lang="ts">
import {computed, ref, watch} from "vue";
import {useRoute} from "vue-router";
import {filtersFromQuery, queryFromFilters} from "../reading/filterLocation";
import {readingLibrary as library, MAX_IMPORT_BYTES, type FontSize} from "../reading/library";
import {formatDateTime} from "../utils/time";
import "../reading/reading.css";

const query = ref("");
const unreadOnly = ref(false);
const message = ref("");
const importing = ref(false);
const route = useRoute();
const returnTo = computed(() => ({name: "home", query: queryFromFilters(filtersFromQuery(route.query))}));
const visible = computed(() => library.state.bookmarks.filter(b =>
  (!unreadOnly.value || !library.state.read.includes(b.url)) && `${b.title} ${b.source_name}`.toLocaleLowerCase().includes(query.value.trim().toLocaleLowerCase())));
watch(() => library.state.font, font => { document.documentElement.dataset.readingFont = font; }, {immediate: true});

function exportFile() {
  const url = URL.createObjectURL(new Blob([library.exportBookmarks()], {type: "application/json"}));
  const a = document.createElement("a");
  a.href = url; a.download = `news-bookmarks-${new Date().toISOString().slice(0, 10)}.json`;
  a.click(); window.setTimeout(() => URL.revokeObjectURL(url), 1000);
  message.value = "已生成收藏备份文件，不包含已读记录。请确认浏览器已完成下载。";
}
async function importFile(event: Event) {
  const input = event.target as HTMLInputElement;
  const file = input.files?.[0];
  if (!file) return;
  importing.value = true;
  try {
    if (file.size > MAX_IMPORT_BYTES) throw new Error("文件超过 2 MB，未导入。");
    const count = library.importBookmarks(await file.text());
    message.value = `已合并 ${count} 条新收藏，重复链接未覆盖。`;
  } catch (e) { message.value = e instanceof Error ? e.message : "导入失败，原有收藏未更改。"; }
  finally { importing.value = false; input.value = ""; }
}
</script>

<template>
  <section class="reading-page" aria-labelledby="library-title">
    <RouterLink :to="returnTo">返回新闻</RouterLink>
    <h1 id="library-title">我的收藏</h1>
    <p>保留原始标题、摘要、来源及链接，不保存全文。最多 500 条，仅存于当前浏览器；清除站点数据会丢失收藏，请定期导出。</p>
    <div class="reading-row">
      <input v-model="query" type="search" aria-label="搜索收藏" placeholder="搜索收藏标题或来源" maxlength="200">
      <label><input v-model="unreadOnly" type="checkbox"> 仅看未读</label>
      <label>阅读字号 <select aria-label="阅读字号" :value="library.state.font" @change="library.setFont(($event.target as HTMLSelectElement).value as FontSize)"><option value="normal">标准</option><option value="large">大</option><option value="larger">特大</option></select></label>
      <button type="button" @click="exportFile">导出收藏</button>
      <label class="reading-import">导入收藏 <input type="file" aria-label="导入收藏" accept="application/json,.json" :disabled="importing" @change="importFile"></label>
    </div>
    <p v-if="message" role="status">{{ message }}</p>
    <p v-if="library.state.warning" role="alert">{{ library.state.warning }}</p>
    <p>{{ visible.length }} / {{ library.state.bookmarks.length }} 条收藏</p>
    <p v-if="!visible.length">{{ library.state.bookmarks.length ? '没有匹配的收藏，可调整搜索条件。' : '还没有收藏。在新闻卡片中选择“收藏”即可留待以后阅读。' }}</p>
    <article v-for="b in visible" :key="b.url" class="reading-bookmark">
      <p>{{ b.source_name }} · <time :datetime="b.published_at">{{ formatDateTime(b.published_at) }}</time></p>
      <h2 :lang="b.language"><a :href="b.url" target="_blank" rel="noopener noreferrer">{{ b.title }}</a></h2>
      <p v-if="b.summary" :lang="b.language">{{ b.summary }}</p>
      <div class="reading-actions">
        <button type="button" :aria-pressed="library.state.read.includes(b.url)" @click="library.toggleRead(b.url)">{{ library.state.read.includes(b.url) ? '已读' : '标为已读' }}</button>
        <button type="button" :aria-label="`移除收藏：${b.title}`" @click="library.removeBookmark(b.url)">移除收藏</button>
      </div>
    </article>
  </section>
</template>
