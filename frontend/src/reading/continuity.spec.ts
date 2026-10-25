import {describe, expect, it} from 'vitest';
import {createContinuity, parseContinuity, MAX_FOLLOWS} from './continuity';
import type {NewsEvent, EventIndex} from '../types/events';
const id = (n: number) => `e_${n.toString(16).padStart(24,'0')}`;
const event = (n = 1, articles = ['a_1','a_2']): NewsEvent => ({event_id:id(n), title:`Event ${n}`, article_ids:articles,
  article_count:articles.length, language:'en', first_published_at:'2026-10-25T00:00:00Z', last_published_at:'2026-10-25T00:00:00Z',
  publisher_ids:['p_1'], publisher_count:1, source_names:['Publisher']});
const filters = {q:'中文', region:'japan', category:'science', language:'ja', source:'nhk'};
const disk = () => { const data = new Map<string,string>(); return {getItem:(key:string)=>data.get(key)??null,setItem:(key:string,value:string)=>{data.set(key,value);}}; };
describe('continuous reading', () => {
  it('persists follows and computes distinct newly collected article IDs', () => {
    const storage=disk(); const a=createContinuity(storage); a.toggleFollow(event());
    const b=createContinuity(storage); expect(b.newCount(event(1,['a_2','a_1']))).toBe(0);
    expect(b.newCount(event(1,['a_2','a_3','a_3']))).toBe(1);
    b.markSeen(event(1,['a_2','a_3'])); expect(b.newCount(event(1,['a_1','a_2','a_3']))).toBe(0);
  });
  it('retains absent events and merges alias histories without duplicate follows', () => {
    const a=createContinuity(disk()); a.toggleFollow(event(1,['a_1'])); a.toggleFollow(event(2,['a_2']));
    a.synchronize({events:[event(2,['a_1','a_2','a_3'])], aliases:{[id(1)]:id(2)}} as EventIndex);
    expect(a.state.follows).toHaveLength(1); expect(a.newCount(event(2,['a_1','a_2','a_3']))).toBe(1);
    a.synchronize({events:[]} as unknown as EventIndex); expect(a.state.follows).toHaveLength(1);
  });
  it('saves, edits and restores raw filter values', () => {
    const storage=disk(); const a=createContinuity(storage); a.saveView('日本科学', filters);
    const view=a.state.views[0]; a.saveView('改名', {...filters,q:'地震'}, view.id);
    expect(createContinuity(storage).state.views).toEqual([{id:view.id,name:'改名',filters:{...filters,q:'地震'}}]);
    a.removeView(view.id); expect(a.state.views).toHaveLength(0);
  });
  it('round trips bounded backup and merges without overwriting existing views', () => {
    const a=createContinuity(disk()); a.toggleFollow(event()); a.saveView('原方案',filters);
    const backup=a.exportBackup(); const b=createContinuity(disk()); b.importBackup(backup);
    const view=b.state.views[0]; b.saveView('本机修改',filters,view.id); b.importBackup(backup);
    expect(b.state.follows).toHaveLength(1); expect(b.state.views[0].name).toBe('本机修改');
  });
  it('rejects an invalid import atomically', () => {
    const a=createContinuity(disk()); a.toggleFollow(event()); const before=a.exportBackup();
    const bad=JSON.parse(before); bad.views=[{id:'x',name:'unsafe',filters:{...filters,source:['bad']}}];
    expect(()=>a.importBackup(JSON.stringify(bad))).toThrow(); expect(a.exportBackup()).toBe(before);
  });
  it('preserves corrupted disk after later user actions', () => {
    const storage=disk(); storage.setItem('broken','{bad'); const a=createContinuity(storage,'broken');
    a.toggleFollow(event()); expect(storage.getItem('broken')).toBe('{bad'); expect(a.state.warning).toContain('阻止覆盖');
  });
  it('retains in-memory work on quota failure without claiming persistence', () => {
    const a=createContinuity({getItem:()=>null,setItem:()=>{throw new Error('Quota');}}); a.toggleFollow(event());
    expect(a.state.follows).toHaveLength(1); expect(a.state.warning).toContain('未能保存');
  });
  it('does not overwrite another tab before its storage event is delivered', () => {
    const storage=disk(); const a=createContinuity(storage); const b=createContinuity(storage);
    a.toggleFollow(event(1)); b.toggleFollow(event(2)); expect(createContinuity(storage).state.follows[0].event_id).toBe(id(1));
    expect(b.state.warning).toContain('其他页面');
  });
  it('enforces follow and total seen-ID limits before mutating', () => {
    const a=createContinuity(null); const data=JSON.parse(a.exportBackup());
    data.follows=Array.from({length:MAX_FOLLOWS},(_,i)=>({event_id:id(i+1),title:'T',followed_at:'2026-10-25T00:00:00Z',seen_article_ids:[]}));
    a.importBackup(JSON.stringify(data)); expect(()=>a.toggleFollow(event(101))).toThrow(); expect(a.state.follows).toHaveLength(100);
    data.follows[0].seen_article_ids=Array.from({length:10001},(_,i)=>`a_${i}`); expect(()=>parseContinuity(JSON.stringify(data))).toThrow();
  });
  it('rejects unsupported or duplicate identities and oversized files', () => {
    const a=createContinuity(null); a.toggleFollow(event()); const data=JSON.parse(a.exportBackup());
    expect(()=>parseContinuity(JSON.stringify({...data,schema_version:2}))).toThrow();
    expect(()=>parseContinuity(JSON.stringify({...data,follows:[data.follows[0],data.follows[0]]}))).toThrow();
    expect(()=>parseContinuity('x'.repeat(2*1024*1024+1))).toThrow();
  });
});
