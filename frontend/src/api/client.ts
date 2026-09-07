const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";

export interface HealthInfo {
  status: string;
  app_name: string;
  app_version: string;
  environment: string;
  database_connected: boolean;
  checked_at: string;
}

export async function getHealth(): Promise<HealthInfo> {
  const res = await fetch(`${API_BASE_URL}/api/v1/health`);
  if (!res.ok) {
    throw new Error(`Health check failed: ${res.status}`);
  }

  return res.json();
}
