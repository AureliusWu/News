<script setup lang="ts">
import {onMounted} from "vue";
import {storeToRefs} from "pinia";
import {useHealthStore} from "@/stores/health";

const healthStore = useHealthStore();
const {loading, error, data, statusLabel} = storeToRefs(healthStore);

onMounted(() => {
  healthStore.fetchHealth();
});
</script>

<template>
  <section class="space-y-4 rounded-xl bg-white p-6 shadow-sm">
    <div>
      <h1 class="text-2xl font-bold">Global News</h1>
      <p class="text-sm text-slate-600">World news, organized by events.</p>
    </div>

    <div class="text-sm text-slate-700">
      <p class="font-semibold">Backend Health</p>
      <div v-if="loading">Checking backend status...</div>
      <div v-else-if="error" class="text-rose-600">{{ error }}</div>
      <div v-else>
        <p>{{ statusLabel }} / DB {{ data?.database_connected ? "connected" : "disconnected" }}</p>
        <p>
          {{ data?.app_name }} {{ data?.app_version }} · {{ data?.environment }}
        </p>
        <p class="text-xs text-slate-500">Checked at {{ data?.checked_at }}</p>
      </div>
    </div>
  </section>
</template>
