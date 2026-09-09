const configuredApiBaseUrl = import.meta.env.VITE_API_BASE_URL?.trim();
const spaBasePath = (import.meta.env.BASE_URL || "/").trim();
const HEALTH_ROUTE = "api/v1/health";

function normalizeBase(base: string): string {
  const trimmed = base.trim();
  if (!trimmed) {
    return "/";
  }

  if (trimmed.startsWith("http://") || trimmed.startsWith("https://")) {
    return trimmed.replace(/\/+$/, "");
  }

  if (trimmed.startsWith("/")) {
    return trimmed === "/" ? "/" : trimmed.replace(/\/+$/, "");
  }

  return `/${trimmed.replace(/\/+$/, "")}`;
}

function joinPath(base: string, path: string): string {
  if (base === "/") {
    return `/${path}`;
  }

  return `${base}/${path}`;
}

export function resolveHealthEndpoint(): string {
  const base = normalizeBase(configuredApiBaseUrl || spaBasePath);
  return joinPath(base, HEALTH_ROUTE);
}

const API_ENDPOINT = resolveHealthEndpoint();

export interface HealthInfo {
  status: string;
  app_name: string;
  app_version: string;
  environment: string;
  database_connected: boolean;
  checked_at: string;
}

export async function getHealth(): Promise<HealthInfo> {
  const res = await fetch(API_ENDPOINT);
  if (!res.ok) {
    throw new Error(`Health check failed: ${res.status}`);
  }

  return res.json();
}
