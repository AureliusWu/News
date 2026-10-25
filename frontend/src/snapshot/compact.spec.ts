import {describe, expect, it, vi} from 'vitest';
import {expandCompact} from './compact';
import {createSnapshotFetch, validateSnapshot} from './transport';
const now = Date.parse('2026-10-25T06:00:00Z');
const source = {id:1,slug:'one',name:'One',publisher:'One',homepage:'https://example.org/',country:'GB',region:'world',language:'en',category:'world',source_type:'official_rss',health_status:'ok',enabled:true};
const article = {id:0,title:'Original headline',summary:null,url:'https://example.org/story',image_url:null,source,published_at:'2026-10-25T05:00:00Z',region:'world',category:'world',language:'en'};
const snapshot = {schema_version:1,snapshot_id:'a'.repeat(24),generated_at:'2026-10-25T05:50:00Z',content_sha256:'a'.repeat(64),
  articles:[article],sources:[source],health:{configured:1,healthy:1,failed:0,gate_pass:true},
  meta:{version:'producer',regions:['world'],categories:['world'],languages:['en'],source_count:1,article_count:1,last_sync_at:'2026-10-25T05:50:00Z',publication_mode:'snapshot'}};
function wire() {const {source: _source,...fields}=article; return {wire_schema_version:1,snapshot:{...snapshot,articles:[{...fields,source_index:0}]}};}
describe('lossless compact news', () => {
  it('preserves every article/source field, null, zero, generation and timestamps', () => {
    expect(expandCompact(wire())).toEqual(snapshot);
    expect(validateSnapshot(expandCompact(wire()),now)).toEqual(snapshot);
  });
  it.each([-1,1,0.5,'0',null])('rejects invalid source index %s', value => {
    const data=wire(); (data.snapshot.articles[0] as Record<string,unknown>).source_index=value;
    expect(()=>expandCompact(data)).toThrow();
  });
  it('rejects ambiguous embedded sources, duplicate identities and unknown versions', () => {
    const data=wire(); Object.assign(data.snapshot.articles[0],{source}); expect(()=>expandCompact(data)).toThrow();
    expect(()=>expandCompact({...wire(),wire_schema_version:2})).toThrow();
    const duplicate=wire(); duplicate.snapshot.sources=[source,source]; expect(()=>expandCompact(duplicate)).toThrow();
  });
  it('uses one compact request and preserves legacy pagination response', async () => {
    const native=vi.fn(async()=>Response.json(wire()));
    const request=createSnapshotFetch(native as typeof fetch,{origin:'https://news.test',basePath:'/News/',compact:true,now:()=>now});
    const response=await request('https://news.test/api/v1/news'); expect((await response.json()).items).toEqual([article]);
    expect(native).toHaveBeenCalledTimes(1); expect(native.mock.calls[0]).toBeDefined();
  });
  it('falls back to the original snapshot only for older deployments with no compact endpoint', async () => {
    const native=vi.fn().mockResolvedValueOnce(new Response('',{status:404})).mockResolvedValueOnce(Response.json(snapshot));
    const request=createSnapshotFetch(native,{origin:'https://news.test',basePath:'/News/',compact:true,now:()=>now});
    expect((await (await request('https://news.test/api/v1/news')).json()).items).toEqual([article]);
    expect(native.mock.calls.map(call=>call[0])).toEqual(['https://news.test/News/data/news.compact.json','https://news.test/News/data/news.json']);
  });
  it('does not reinterpret corrupt compact input as a different unbound generation', async () => {
    const native=vi.fn(async()=>Response.json({...wire(),wire_schema_version:2}));
    const request=createSnapshotFetch(native as typeof fetch,{origin:'https://news.test',basePath:'/News/',compact:true,now:()=>now});
    await expect(request('https://news.test/api/v1/news')).rejects.toThrow(); expect(native).toHaveBeenCalledTimes(1);
  });
});
