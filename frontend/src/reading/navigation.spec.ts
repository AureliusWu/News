import {afterEach, describe, expect, it} from "vitest";
import {defineComponent, h, reactive} from "vue";
import {mount, flushPromises, type VueWrapper} from "@vue/test-utils";
import {createMemoryHistory, createRouter, RouterView} from "vue-router";
import ReadingToolbar from "../components/ReadingToolbar.vue";
import LibraryView from "../pages/LibraryView.vue";
import SourcesView from "../pages/SourcesView.vue";
import type {NewsFilters} from "../types/news";

let wrapper: VueWrapper | undefined;
afterEach(() => { wrapper?.unmount(); wrapper = undefined; });
describe("reading navigation", () => {
  async function open(path: string) {
    const filters = reactive<NewsFilters>({q: "", region: "", category: "", language: "", source: ""});
    const Home = defineComponent({setup: () => () => h(ReadingToolbar, {filters})});
    const router = createRouter({history: createMemoryHistory(), routes: [
      {path: "/", name: "home", component: Home},
      {path: "/library", component: LibraryView},
      {path: "/sources", component: SourcesView}
    ]});
    await router.push(path); await router.isReady();
    wrapper = mount(defineComponent({setup: () => () => h(RouterView)}), {global: {plugins: [router]}});
    await flushPromises();
    return {router, filters};
  }
  it.each(["library", "sources"])("preserves filters through %s and return", async page => {
    const {router, filters} = await open("/?region=japan&language=ja&q=中文&token=ignored");
    expect(filters.region).toBe("japan");
    const link = wrapper!.findAll("a").find(a => a.attributes("href")?.includes(`/${page}`))!;
    expect(link.attributes("href")).not.toContain("token");
    await link.trigger("click", {button: 0}); await flushPromises();
    expect(router.currentRoute.value.path).toBe(`/${page}`);
    await wrapper!.findAll("a").find(a => a.text() === "返回新闻")!.trigger("click"); await flushPromises();
    expect(router.currentRoute.value.query).toEqual({q: "中文", region: "japan", language: "ja"});
    expect(filters.q).toBe("中文");
  });
  it("restores filters on direct library deep link after refresh", async () => {
    const {router} = await open("/library?source=nhk-japan&category=science&token=ignored");
    await wrapper!.findAll("a").find(a => a.text() === "返回新闻")!.trigger("click"); await flushPromises();
    expect(router.currentRoute.value.query).toEqual({category: "science", source: "nhk-japan"});
  });
});
