<script setup lang="ts">
import {RouterLink, RouterView} from "vue-router";
</script>

<template>
  <div class="min-h-screen bg-slate-50 text-slate-900">
    <header class="border-b border-slate-200 bg-white px-4 py-4">
      <nav class="mx-auto flex w-full max-w-4xl items-center justify-between">
        <RouterLink class="text-lg font-semibold" to="/">Global News</RouterLink>
        <RouterLink to="/about" class="text-sm text-slate-600 hover:underline">About</RouterLink>
      </nav>
    </header>

    <main class="mx-auto w-full max-w-4xl p-4">
      <RouterView />
    </main>
  </div>
</template>
