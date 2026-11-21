import { useAsync } from './useAsync.js';
import { api } from '../api/sentinelApi.js';

const FALLBACK = { branches: ['Boston'], chatSuggestions: [] };

export function useMeta() {
  const { data } = useAsync(() => api.meta(), []);
  return data ?? FALLBACK;
}
