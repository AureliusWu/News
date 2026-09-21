import { installSnapshotTransport } from './snapshot/transport';

// Install only the explicitly selected publication adapter before Vue mounts.
// Native/API mode continues using the original client and backend unchanged.
if (import.meta.env.VITE_NEWS_MODE === 'snapshot') {
  installSnapshotTransport(import.meta.env.BASE_URL);
}
void import('./main');
