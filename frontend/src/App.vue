<script setup lang="ts">
import {RouterLink, RouterView} from "vue-router";
import {ui} from "./locales/zh-CN";
</script>
<template>
  <div class="app-shell">
    <a class="skip-link" href="#main-content">{{ ui.navigation.skip }}</a>
    <header class="site-header"><nav class="header-inner" :aria-label="ui.navigation.main">
      <RouterLink class="brand" to="/" :title="ui.brand.english"><span class="brand-mark" aria-hidden="true">G</span>{{ ui.brand.name }}</RouterLink>
      <div class="header-links"><span class="edition">{{ ui.navigation.edition }}</span><RouterLink to="/about">{{ ui.navigation.about }}</RouterLink></div>
    </nav></header>
    <main id="main-content" class="main-content"><RouterView /></main>
    <footer class="site-footer">{{ ui.brand.full }} <span>V0.2.0</span> <span>{{ ui.navigation.copyright }}</span></footer>
  </div>
</template>
