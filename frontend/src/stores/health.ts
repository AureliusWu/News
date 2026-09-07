import {defineStore} from "pinia";
import {computed, ref} from "vue";
import {getHealth, type HealthInfo} from "@/api/client";

export const useHealthStore = defineStore("health", () => {
  const loading = ref(false);
  const error = ref<string | null>(null);
  const data = ref<HealthInfo | null>(null);

  const statusLabel = computed(() => {
    if (error.value) {
      return "Unavailable";
    }

    return data.value?.status ?? "Unknown";
  });

  async function fetchHealth() {
    loading.value = true;
    error.value = null;
    try {
      data.value = await getHealth();
    } catch (e) {
      error.value = e instanceof Error ? e.message : "Unknown error";
      data.value = null;
    } finally {
      loading.value = false;
    }
  }

  return {
    loading,
    error,
    data,
    statusLabel,
    fetchHealth
  };
});
