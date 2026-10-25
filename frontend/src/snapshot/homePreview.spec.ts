import {describe, expect, it, vi} from 'vitest';
import {createSnapshotFetch} from './transport';
import type {Snapshot} from './transport';
const now=Date.parse('2026-10-25T08:00:00Z');
const source={id:1,slug:'one',name:'One',publisher:'Original',homepage:'https://example.org/',country:'GB',region:'world',language:'en',category:'world',source_type:'official_rss',health_status:'ok',enabled:true};
function full(): Snapshot {
  return {schema_version:1,generated_at:'2026-10-25T07:50:00Z',snapshot_id:'a'.repeat(24),content_sha256:'a'.repeat(64),sources:[source],
    articles:Array.from({length:35},(_,id)=>({id,title:`Headline ${id}`,summary:null,url:`https://example.org/${id}`,image_url:null,
      source,published_at:'2026-10-25T07:30:00Z',region:'world',category:'world',language:'en'})),
    health:{configured:1,healthy:1,failed:0,gate_pass:true},meta:{version:'producer',regions:['world'],categories:['world'],languages:['en'],source_count:1,article_count:35,last_sync_at:'2026-10-25T07:50:00Z',publication_mode:'snapshot'}};
}
function compact(snapshot=full()) {return {wire_schema_version:1,snapshot:{...snapshot,articles:snapshot.articles.map(article=>{const {source:_source,...fields}=article;return {...fields,source_index:0};})}};}
function home(snapshot=full()) {const wire=compact(snapshot);return {...wire,view:'home-preview-v1',total_articles:snapshot.articles.length,snapshot:{...wire.snapshot,articles:wire.snapshot.articles.slice(0,30)}};}
const options={origin:'https://news.test',basePath:'/News/',compact:true,homePreview:true,now:()=>now};
const url=(path:string)=>`https://news.test/api/v1/${path}`;
describe('bound first-page snapshot',()=>{
  it('does not wait forever for a blocked cache during offline fallback',async()=>{
    vi.useFakeTimers();
    try {
      const storage={open:()=>new Promise(()=>{})} as unknown as CacheStorage;
      const request=createSnapshotFetch(vi.fn(async()=>{throw new Error('Offline');}) as typeof fetch,{...options,storage});
      const rejected=expect(request(url('meta'))).rejects.toThrow();
      await vi.advanceTimersByTimeAsync(2000);await rejected;
    } finally {vi.useRealTimers();}
  });
  it('prefers a newer partial generation to an older valid full cache for unfiltered offline reading',async()=>{
    const previous={...full(),generated_at:'2026-10-25T06:00:00Z'};
    const storage={open:async()=>({match:async(key:string)=>Response.json(key.endsWith('news.home.json')?home():previous)})} as unknown as CacheStorage;
    const request=createSnapshotFetch(vi.fn(async()=>{throw new Error('Offline');}) as typeof fetch,{...options,storage});
    const response=await request(url('news?limit=30'));expect(response.headers.get('X-News-Generated-At')).toBe(full().generated_at);
    expect((await response.json()).items).toEqual(full().articles.slice(0,30));
  });
  it('shares one small request for first page, metadata and sources while preserving total and cursor',async()=>{
    const native=vi.fn(async(_input:RequestInfo|URL)=>Response.json(home()));const request=createSnapshotFetch(native as typeof fetch,options);
    const results=await Promise.all([request(url('meta')),request(url('news?limit=30')),request(url('sources'))]);
    expect((await results[0].json()).article_count).toBe(35);
    const page=await results[1].json();expect(page.items).toEqual(full().articles.slice(0,30));expect(page.has_more).toBe(true);expect(page.next_cursor).toBeTruthy();
    expect(native).toHaveBeenCalledTimes(1);expect(native.mock.calls[0][0]).toBe('https://news.test/News/data/news.home.json');
  });
  it('loads full data for pagination without dropping or duplicating articles',async()=>{
    const native=vi.fn(async(input:RequestInfo|URL)=>Response.json(String(input).endsWith('news.home.json')?home():compact()));
    const request=createSnapshotFetch(native as typeof fetch,options);
    const first=await(await request(url('news?limit=30'))).json();
    const second=await(await request(url(`news?limit=30&cursor=${encodeURIComponent(first.next_cursor)}`))).json();
    expect([...first.items,...second.items]).toEqual(full().articles);expect(second.has_more).toBe(false);expect(native).toHaveBeenCalledTimes(2);
  });
  it('filters and event snapshot requests always use full data',async()=>{
    const native=vi.fn(async(_input:RequestInfo|URL)=>Response.json(compact()));const request=createSnapshotFetch(native as typeof fetch,options);
    const filtered=await(await request(url('news?q=Headline%2034'))).json();expect(filtered.items[0].id).toBe(34);
    expect((await(await request(url('snapshot'))).json()).articles).toHaveLength(35);expect(native).toHaveBeenCalledTimes(1);
    expect(native.mock.calls[0][0]).toBe('https://news.test/News/data/news.compact.json');
  });
  it('older publishers fall back on 404 without representing full data as a partial cache',async()=>{
    const native=vi.fn().mockResolvedValueOnce(new Response('',{status:404})).mockResolvedValueOnce(Response.json(compact()));
    const request=createSnapshotFetch(native,options);await request(url('news?limit=30'));
    expect((await(await request(url('snapshot'))).json()).articles).toHaveLength(35);expect(native).toHaveBeenCalledTimes(2);
  });
  it('rejects inconsistent coverage rather than silently switching to another generation',async()=>{
    for(const change of [(value:ReturnType<typeof home>)=>value.total_articles=34,
      (value:ReturnType<typeof home>)=>value.snapshot.articles.pop()]) {
      const value=home();change(value);const native=vi.fn(async()=>Response.json(value));
      const request=createSnapshotFetch(native as typeof fetch,options);await expect(request(url('meta'))).rejects.toThrow();expect(native).toHaveBeenCalledTimes(1);
    }
  });
  it('retains the full request when it arrives during homepage warmup',async()=>{
    let release!:(value:Response)=>void;
    const native=vi.fn().mockImplementationOnce(()=>new Promise<Response>(resolve=>{release=resolve;})).mockResolvedValueOnce(Response.json(compact()));
    const request=createSnapshotFetch(native,options);const meta=request(url('meta'));const entire=request(url('snapshot'));
    release(Response.json(home()));expect((await(await meta).json()).article_count).toBe(35);
    expect((await(await entire).json()).articles).toHaveLength(35);expect(native).toHaveBeenCalledTimes(2);
  });
  it('cached first-page data is reusable offline but never supplies a full filtered dataset',async()=>{
    const saved=new Map<string,Response>();
    const storage={open:async()=>({put:async(key:string,value:Response)=>{saved.set(key,value.clone());},match:async(key:string)=>saved.get(key)?.clone()})} as unknown as CacheStorage;
    const request=createSnapshotFetch(vi.fn(async()=>Response.json(home())) as typeof fetch,{...options,storage});
    await request(url('news?limit=30'));await vi.waitFor(()=>expect(saved.has('https://news.test/News/data/news.home.json')).toBe(true));
    expect(saved.has('https://news.test/News/data/news.json')).toBe(false);
    const offline=createSnapshotFetch(vi.fn(async()=>{throw new Error('Offline');}) as typeof fetch,{...options,storage});
    const page=await offline(url('news?limit=30'));expect(page.headers.get('X-Cache-Stale')).toBe('true');expect((await page.json()).items).toHaveLength(30);
    await expect(offline(url('news?q=Headline%2034'))).rejects.toThrow();
  });
  it('a full generation change returns the existing cursor-conflict response',async()=>{
    const changed={...full(),content_sha256:'b'.repeat(64),snapshot_id:'b'.repeat(24)};
    const native=vi.fn(async(input:RequestInfo|URL)=>Response.json(String(input).endsWith('news.home.json')?home():compact(changed)));
    const request=createSnapshotFetch(native as typeof fetch,options);const first=await(await request(url('news?limit=30'))).json();
    expect((await request(url(`news?limit=30&cursor=${encodeURIComponent(first.next_cursor)}`))).status).toBe(409);
  });
});
