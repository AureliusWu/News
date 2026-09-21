<script setup lang="ts">
import {ui} from "../locales/zh-CN";
const snapshotMode = import.meta.env.VITE_NEWS_MODE === "snapshot";
</script>

<template>
  <section class="about-page">
    <p class="eyebrow">{{ ui.brand.full }} / V0.2.0</p>
    <h1>{{ ui.about.title }}</h1>
    <p>{{ ui.about.introduction }}</p>
    <h2>{{ ui.about.sourcesTitle }}</h2>
    <p>{{ ui.about.sources }}</p>
    <h2>{{ ui.about.updatesTitle }}</h2>
    <p>{{ snapshotMode ? ui.about.snapshotUpdates : ui.about.apiUpdates }}</p>
    <p>{{ ui.about.timestamps }}</p>
    <h2>{{ ui.about.offlineTitle }}</h2>
    <p>{{ ui.about.offline }}</p>
  </section>
</template>
