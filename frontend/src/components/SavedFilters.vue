<script setup lang="ts">
import {computed, ref, watch} from 'vue';
import type {NewsFilters, NewsSource} from '../types/news';
import {continuity} from '../reading/continuity';
const props = defineProps<{filters: NewsFilters; sources?: NewsSource[]}>();
const selected = ref(''); const name = ref(''); const message = ref('');
const saved = computed(() => continuity.state.views.find(item => item.id === selected.value));
watch(selected, () => { name.value = saved.value?.name ?? ''; message.value = ''; });
function save() {
  try { continuity.saveView(name.value, props.filters, selected.value || undefined); message.value = continuity.state.warning || '筛选方案已保存。'; }
  catch (e) { message.value = e instanceof Error ? e.message : '保存失败。'; }
}
function apply() {
  if (!saved.value) return;
  Object.assign(props.filters, saved.value.filters);
  const source = saved.value.filters.source;
  message.value = source && props.sources?.length && !props.sources.some(item => item.slug === source || String(item.id) === source)
    ? '原来源目前不可用，已保留筛选条件；可在来源筛选中重新选择。' : '已应用筛选方案。';
}
function remove() { continuity.removeView(selected.value); selected.value = ''; }
</script>
<template>
  <details class="saved-filters">
    <summary>我的筛选方案（{{ continuity.state.views.length }}）</summary>
    <p>保存当前地区、分类、语言、来源和关键词，最多 20 个方案，仅存于当前浏览器。</p>
    <div class="reading-row">
      <label>已存方案 <select v-model="selected" aria-label="已存筛选方案"><option value="">新建方案</option><option v-for="item in continuity.state.views" :key="item.id" :value="item.id">{{ item.name }}</option></select></label>
      <button type="button" :disabled="!saved" @click="apply">应用方案</button>
      <button type="button" :disabled="!saved" @click="remove">删除方案</button>
    </div>
    <form class="reading-row" @submit.prevent="save">
      <label>方案名称 <input v-model="name" type="text" aria-label="方案名称" maxlength="40" required></label>
      <button type="submit" :disabled="!name.trim()">{{ saved ? '更新方案' : '保存当前筛选' }}</button>
    </form>
    <p v-if="message" role="status">{{ message }}</p>
    <p v-if="continuity.state.warning" role="alert">{{ continuity.state.warning }}</p>
  </details>
</template>
