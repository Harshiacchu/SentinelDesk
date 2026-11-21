import { useAsync } from './useAsync.js';
import { api } from '../api/sentinelApi.js';

const FALLBACK = { chatSuggestions: [] };

export function useMeta() {
  const { data } = useAsync(() => api.meta(), []);
  return data ?? FALLBACK;
}
