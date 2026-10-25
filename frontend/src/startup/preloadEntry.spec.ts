import {describe, expect, it} from 'vitest';
import {startupTags} from '../../build/preload-entry';
describe('startup resource discovery', () => {
  const bundle={main:{type:'chunk',name:'main',fileName:'assets/main-hash.js'},
    styles:{type:'asset',fileName:'assets/main-hash.css'},events:{type:'chunk',name:'EventsView',fileName:'assets/EventsView-lazy.js'}};
  it.each(['/','/News/'])('discovers main resources at %s without eagerly loading event routes', base => {
    const tags=startupTags(bundle,base);
    expect(tags.map(tag=>tag.attrs?.href)).toEqual([`${base}assets/main-hash.js`,`${base}assets/main-hash.css`]);
    expect(tags[0].attrs?.rel).toBe('modulepreload');expect(tags[1].attrs?.rel).toBe('stylesheet');
  });
  it('does not invent an asset when there is no main application chunk', () => {expect(startupTags({},'/News/')).toEqual([]);});
});
