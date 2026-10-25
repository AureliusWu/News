import type {HtmlTagDescriptor, Plugin} from 'vite';

type Bundles = Record<string, {type: string; name?: string; fileName: string}>;
export function startupTags(bundle: Bundles, base: string): HtmlTagDescriptor[] {
  const main = Object.values(bundle).find(item => item.type === 'chunk' && item.name === 'main');
  if (!main) return [];
  const tags: HtmlTagDescriptor[] = [{tag:'link',attrs:{rel:'modulepreload',href:base+main.fileName,crossorigin:''},injectTo:'head'}];
  for (const item of Object.values(bundle)) {
    if (item.type === 'asset' && /^assets\/main-[^/]+\.css$/.test(item.fileName))
      tags.push({tag:'link',attrs:{rel:'stylesheet',href:base+item.fileName,crossorigin:''},injectTo:'head'});
  }
  return tags;
}
export function preloadStartup(): Plugin {
  let base = '/';
  return {name:'news-preload-startup',apply:'build',
    configResolved(config) {base=config.base;},
    transformIndexHtml:{order:'post',handler(_html,context) {return startupTags(context.bundle || {},base);}}};
}
