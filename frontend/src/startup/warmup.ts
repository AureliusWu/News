import type {NewsProvider} from '../api/providers';

type Options = {
  mode: string | undefined;
  pathname: string;
  basePath: string;
  resolveProvider: () => Pick<NewsProvider, 'mode' | 'request'>;
};

export function warmSnapshotHome(options: Options): Promise<void> | undefined {
  if (options.mode !== 'snapshot' ||
      options.pathname.replace(/\/+$/, '') !== options.basePath.replace(/\/+$/, '')) return;
  try {
    const provider = options.resolveProvider();
    if (provider.mode !== 'snapshot') return;
    return provider.request('meta').then(() => undefined, () => undefined);
  } catch {
    // Optional startup work must leave errors to the normal page request.
    return;
  }
}
