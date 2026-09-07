import {config} from "@vue/test-utils";
import {createPinia} from "pinia";

config.global.plugins = [createPinia()];import {render, screen} from "@testing-library/vue";
import {describe, it, vi} from "vitest";
import HomeView from "../HomeView.vue";

vi.stubGlobal("fetch", vi.fn(() =>
  Promise.resolve({
    ok: true,
      json: () =>
      Promise.resolve({
        status: "healthy",
        app_name: "Global News",
        app_version: "0.1.1",
        environment: "development",
        database_connected: true,
        checked_at: new Date().toISOString()
      })
  } as Response)
));

describe("HomeView", () => {
  it("shows home headline and health status", async () => {
    render(HomeView);
    expect(await screen.findByText("Global News")).toBeTruthy();
    expect(screen.getByText("World news, organized by events.")).toBeTruthy();
  });
});

