export const ui = {
  brand: {name: "全球新闻", english: "Global News", full: "全球新闻 / Global News"},
  navigation: {
    skip: "跳转到新闻", main: "主导航", about: "关于", edition: "从原始来源，了解世界",
    copyright: "新闻内容及图片版权归原发布媒体所有。"
  },
  home: {
    timeline: "新闻时间线", eyebrow: "跨越地域，回到新闻源头。", title: "最新新闻",
    latest: "最新", filtered: "筛选结果", sections: "新闻分类",
    refresh: "刷新", updating: "更新中...", searchPlaceholder: "搜索新闻标题",
    search: "搜索", filters: "筛选新闻", region: "地区", language: "语言", source: "来源",
    allRegions: "全部地区", allLanguages: "全部语言", allSources: "全部来源",
    offline: "当前处于离线状态。", cached: "正在显示缓存新闻。",
    staleHint: "这些内容可能已过时，请联网或刷新以获取最新内容。",
    loading: "正在加载新闻", articles: "新闻列表", loadFailed: "暂时无法加载新闻",
    retry: "重试", firstStories: "首批新闻正在收集中",
    collecting: "正在收集最新新闻，页面将自动更新。", noStories: "没有找到相关新闻",
    changeFilters: "请尝试其他分类或调整搜索条件。", refreshNews: "刷新新闻",
    loadingMore: "正在加载更多新闻...", loadMore: "加载更多", caughtUp: "已显示全部结果。"
  },
  article: {
    original: "阅读原文", originalLabel: (title: string) => `阅读原文：${title}`,
    publishedAt: (time: string) => `原文发布时间：${time}`
  },
  time: {
    unknown: "时间未知", justNow: "刚刚", yesterday: "昨天",
    minutes: (value: number) => `${value} 分钟前`, hours: (value: number) => `${value} 小时前`
  },
  errors: {loadNews: "新闻暂时无法加载，请检查网络或稍后重试。"},
  snapshot: {
    loading: "正在加载已发布的新闻快照，无需实时后端。", refresh: "刷新快照",
    unavailable: "新闻快照暂不可用，请检查网络或稍后重试。",
    normal: "定时快照", delayed: "更新延迟", cached: "缓存快照（可能已过时）",
    summary: (edition: string, updatedAt: string, healthy: number, configured: number) =>
      `${edition} | 快照更新：${updatedAt} | 可用来源：${healthy}/${configured} | 计划约每 30 分钟更新，非实时，可能延迟。`
  },
  about: {
    title: "从更多来源，了解世界。",
    introduction: "按时间浏览各地媒体的报道，使用地区、分类、语言和来源筛选，再前往原发布媒体阅读完整内容。界面使用简体中文，新闻标题和摘要保留原文，不自动翻译。",
    sourcesTitle: "新闻从哪里来",
    sources: "新闻来自媒体的 RSS 或 Atom 订阅源。页面标注来源，并展示原标题、原始发布时间及简短摘录。摘录来自订阅源，不是 AI 生成的摘要。新闻内容和图片版权归原发布媒体所有，媒体名称保留官方名称。",
    updatesTitle: "更新方式与时间",
    snapshotUpdates: "当前为定时快照模式，计划约每 30 分钟更新，调度和采集可能延迟，并非实时资讯。搜索与筛选仅覆盖当前发布的快照，不代表媒体的完整历史内容。访问本站不需要启动本地后端或 Docker。",
    apiUpdates: "当前使用已配置的后端新闻服务，内容随采集任务同步。页面刷新只获取服务已有的数据，不代表媒体刚刚发布了新报道。",
    timestamps: "时间使用中文格式，并按浏览器本地时区显示；完整时间包含时区。新闻卡片使用原媒体的发布时间，快照模式顶部展示快照生成时间，两者不能混用。",
    offlineTitle: "离线与缓存",
    offline: "离线时可以阅读已缓存的新闻列表，页面会显示提示。缓存内容可能已过时，联网后可尝试刷新。阅读媒体原文需要网络连接，部分内容可能需要订阅。"
  }
} as const;

const regions: Readonly<Record<string, string>> = {
  world: "国际", china: "中国", us: "美国", japan: "日本", europe: "欧洲", asia: "亚洲",
  "middle-east": "中东", africa: "非洲", oceania: "大洋洲", americas: "美洲"
};
const categories: Readonly<Record<string, string>> = {
  world: "国际", business: "财经", technology: "科技", science: "科学"
};
const languages: Readonly<Record<string, string>> = {
  zh: "中文", "zh-cn": "简体中文", "zh-hans": "简体中文", "zh-tw": "繁体中文", "zh-hant": "繁体中文",
  en: "英语", ja: "日语", fr: "法语", de: "德语", es: "西班牙语", ar: "阿拉伯语",
  ru: "俄语", pt: "葡萄牙语", ko: "韩语"
};
function displayLabel(labels: Readonly<Record<string, string>>, value: string): string {
  const key = value.toLowerCase();
  return Object.prototype.hasOwnProperty.call(labels, key) ? labels[key] : value;
}
export const regionLabel = (value: string) => displayLabel(regions, value);
export const categoryLabel = (value: string) => displayLabel(categories, value);
export const languageLabel = (value: string) => displayLabel(languages, value);
