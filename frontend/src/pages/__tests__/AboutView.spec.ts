import {afterEach, describe, expect, it, vi} from "vitest";
import {mount, type VueWrapper} from "@vue/test-utils";
import AboutView from "../AboutView.vue";

let wrapper: VueWrapper | undefined;
afterEach(() => { wrapper?.unmount(); wrapper = undefined; vi.unstubAllEnvs(); });

describe("Chinese about page", () => {
  it("describes snapshot limitations without promising a live backend", () => {
    vi.stubEnv("VITE_NEWS_MODE", "snapshot");
    wrapper = mount(AboutView);
    expect(wrapper.find("h1").text()).toBe("从更多来源，了解世界。");
    expect(wrapper.text()).toContain("Global News");
    expect(wrapper.text()).toContain("约每 30 分钟更新");
    expect(wrapper.text()).toContain("不自动翻译");
    expect(wrapper.text()).toContain("不是 AI 生成的摘要");
    expect(wrapper.text()).toContain("快照生成时间，两者不能混用");
    expect(wrapper.text()).not.toContain("当前使用已配置的后端新闻服务");
  });
  it("keeps the native API mode description distinct", () => {
    vi.stubEnv("VITE_NEWS_MODE", "api");
    wrapper = mount(AboutView);
    expect(wrapper.text()).toContain("当前使用已配置的后端新闻服务");
    expect(wrapper.text()).not.toContain("约每 30 分钟更新");
    expect(wrapper.text()).toContain("部分内容可能需要订阅");
  });
});
