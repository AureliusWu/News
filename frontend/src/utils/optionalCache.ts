export function openOptionalCache(storage: CacheStorage | undefined, name: string): Promise<Cache | undefined> {
  const opening = Promise.resolve().then(() => storage?.open(name)).catch(() => undefined);
  if (!storage) return opening;
  let timer: ReturnType<typeof setTimeout> | undefined;
  return Promise.race([opening,new Promise<undefined>(resolve => {timer=setTimeout(()=>resolve(undefined),2000);})])
    .finally(() => {if(timer!==undefined) clearTimeout(timer);});
}
