<script setup lang="ts">
import {ref, watch} from "vue";
import type {NewsArticle} from "../types/news";
import {formatDateTime, formatRelativeTime} from "../utils/time";
import {ui, categoryLabel, regionLabel} from "../locales/zh-CN";
const props = defineProps<{article: NewsArticle; now?: number}>();
const imageFailed = ref(false);
watch(() => props.article.image_url, () => { imageFailed.value = false; });
</script>

<template>
  <article class="news-card" lang="zh-CN" :data-news-id="article.id">
    <div class="time-rail">
      <time :datetime="article.published_at" :title="ui.article.publishedAt(formatDateTime(article.published_at))"
            :aria-label="ui.article.publishedAt(formatDateTime(article.published_at))">
        {{ formatRelativeTime(article.published_at, now) }}
      </time>
    </div>
    <div class="news-body">
      <div class="news-byline">
        <span class="publisher">{{ article.source.name }}</span>
        <span class="news-topic">{{ categoryLabel(article.category) }} / {{ regionLabel(article.region) }}</span>
      </div>
      <h2 :lang="article.language"><a :href="article.url" target="_blank" rel="noopener noreferrer">{{ article.title }}</a></h2>
      <p v-if="article.summary" class="news-summary" :lang="article.language">{{ article.summary }}</p>
      <a class="original-link" :href="article.url" target="_blank" rel="noopener noreferrer"
         :aria-label="ui.article.originalLabel(article.title)">{{ ui.article.original }} <span aria-hidden="true">&#8599;</span></a>
    </div>
    <img v-if="article.image_url && !imageFailed" class="news-image" :src="article.image_url" alt=""
         width="168" height="112" loading="lazy" decoding="async" referrerpolicy="no-referrer"
         @error="imageFailed = true" />
  </article>
</template>
