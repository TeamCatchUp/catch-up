// API ManualSearchHistoryItem → UI SearchHistoryEntry 변환.

import type { SearchHistoryEntry } from '@/shared/types/searchHistory';
import type { ManualSearchHistoryItem } from '@/shared/types/searchHistoryApi';

export function mapSearchHistory(item: ManualSearchHistoryItem): SearchHistoryEntry {
  return {
    id: String(item.id),
    query: item.query,
    createdAt: new Date(item.created_at),
  };
}
