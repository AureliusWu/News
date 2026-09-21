<script setup lang="ts">
import {RouterLink, RouterView} from "vue-router";
</script>
<template>
  <div class="app-shell">
    <a class="skip-link" href="#main-content">Skip to news</a>
    <header class="site-header"><nav class="header-inner" aria-label="Main navigation">
      <RouterLink class="brand" to="/"><span class="brand-mark" aria-hidden="true">G</span>Global News</RouterLink>
      <div class="header-links"><span class="edition">The world, in perspective</span><RouterLink to="/about">About</RouterLink></div>
    </nav></header>
    <main id="main-content" class="main-content"><RouterView /></main>
    <footer class="site-footer">Global News <span>V0.2.0</span> <span>Reporting belongs to its original publisher.</span></footer>
  </div>
</template>