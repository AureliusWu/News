import {getProvider} from './api/providers';
import {warmSnapshotHome} from './startup/warmup';

// Start the same provider's download while the Vue application chunk loads.
if (import.meta.env.VITE_NEWS_MODE === 'snapshot') {
  void warmSnapshotHome({
    mode: import.meta.env.VITE_NEWS_MODE,
    pathname: window.location.pathname,
    basePath: import.meta.env.BASE_URL,
    resolveProvider: getProvider,
  });
}
void import('./main');
