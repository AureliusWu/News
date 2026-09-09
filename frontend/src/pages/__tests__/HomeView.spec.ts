import {config} from "@vue/test-utils";
import {createPinia} from "pinia";
import {createRouter, createWebHistory} from "vue-router";
import {describe, it, vi, beforeEach, afterEach} from "vitest";
import {render, screen, waitFor} from "@testing-library/vue";

import App from "../../App.vue";
import HomeView from "../HomeView.vue";
import routes from "../../router";

config.global.plugins = [createPinia()];

function createFetchResponse(
  overrides: Partial<Response> & {json: () => Promise<unknown>} = {json: () => Promise.resolve({})}
): Response {
  return {
    ok: true,
    ...overrides
  } as Response;
}

describe("HomeView", () => {
  beforeEach(() => {
    vi.unstubAllGlobals();
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
  });

  it("renders headline and subtitle", () => {
    render(HomeView);
    expect(screen.getByText("Global News")).toBeTruthy();
    expect(screen.getByText("World news, organized by events.")).toBeTruthy();
  });

  it("shows backend health status on success", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () =>
        createFetchResponse({
          ok: true,
          json: async () => ({
            status: "healthy",
            app_name: "Global News",
            app_version: "0.1.2",
            environment: "development",
            database_connected: true,
            checked_at: new Date().toISOString()
          })
        })
      )
    );

    render(HomeView);

    expect(await screen.findByText("healthy / DB connected")).toBeTruthy();
    expect(screen.getByText("Global News 0.1.2 · development")).toBeTruthy();
  });

  it("shows error state when request fails", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => Promise.reject(new Error("Health check failed: 500"))));

    render(HomeView);

    expect(await screen.findByText("Health check failed: 500")).toBeTruthy();
  });

  it("calls relative /api/v1/health by default", async () => {
    const fetchMock = vi.fn(async () =>
      createFetchResponse({
        ok: true,
        json: async () => ({
          status: "healthy",
          app_name: "Global News",
          app_version: "0.1.2",
          environment: "development",
          database_connected: true,
          checked_at: new Date().toISOString()
        })
      })
    );
    vi.stubGlobal("fetch", fetchMock);

    render(HomeView);

    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalledTimes(1);
    });

    expect((fetchMock.mock.calls[0]?.[0] ?? "") as string).toContain("/api/v1/health");
  });
});

describe("Router fallback", () => {
  it("redirects unknown routes to home", async () => {
    const router = createRouter({
      history: createWebHistory(import.meta.env.BASE_URL),
      routes
    });
    const fetchMock = vi.fn(async () =>
      createFetchResponse({
        ok: true,
        json: async () => ({
          status: "healthy",
          app_name: "Global News",
          app_version: "0.1.2",
          environment: "development",
          database_connected: true,
          checked_at: new Date().toISOString()
        })
      })
    );
    vi.stubGlobal("fetch", fetchMock);

    router.push("/path-does-not-exist");
    await router.isReady();

    render(App, {
      global: {
        plugins: [router]
      }
    });

    expect(await screen.findByText("Backend Health")).toBeTruthy();
  });
});
