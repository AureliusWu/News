<script setup lang="ts">
import {computed, ref} from "vue";
import type {NewsArticle} from "../types/news";
import {readingLibrary as library} from "../reading/library";
const props = defineProps<{article: NewsArticle}>();
const error = ref("");
const saved = computed(() => library.state.bookmarks.some(b => b.url === props.article.url));
const read = computed(() => library.state.read.includes(props.article.url));
function save() {
  try { library.toggleBookmark(props.article); error.value = ""; }
  catch (e) { error.value = e instanceof Error ? e.message : "收藏失败，请重试。"; }
}
</script>

<template>
  <div class="reading-actions" aria-label="阅读操作">
    <button type="button" :aria-pressed="saved" :aria-label="`${saved ? '取消收藏' : '收藏'}：${article.title}`" @click="save">{{ saved ? '已收藏' : '收藏' }}</button>
    <button type="button" :aria-pressed="read" :aria-label="`${read ? '标为未读' : '标为已读'}：${article.title}`" @click="library.toggleRead(article.url)">{{ read ? '已读' : '标为已读' }}</button>
    <span v-if="error" role="alert">{{ error }}</span>
  </div>
</template>
