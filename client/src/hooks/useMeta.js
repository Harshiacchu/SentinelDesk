import { useAsync } from './useAsync.js';
import { api } from '../api/sentinelApi.js';

const FALLBACK = { translation: false };

/** Server capabilities (e.g. whether translation is configured). */
export function useMeta() {
  const { data } = useAsync(() => api.meta(), []);
  return data ?? FALLBACK;
}
