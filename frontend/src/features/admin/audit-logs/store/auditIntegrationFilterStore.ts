import type { DateRange } from 'react-day-picker';
import { create } from 'zustand';

import type { AuditSortKey } from '../types/auditLog';

interface AuditIntegrationFilterStore {
  sort: AuditSortKey;
  setSort: (sort: AuditSortKey) => void;

  dateRange: DateRange | undefined;
  setDateRange: (range: DateRange | undefined) => void;

  searchTerm: string;
  setSearchTerm: (term: string) => void;
}

export const useAuditIntegrationFilterStore = create<AuditIntegrationFilterStore>((set) => ({
  sort: 'newest',
  setSort: (sort) => set({ sort }),

  dateRange: undefined,
  setDateRange: (dateRange) => set({ dateRange }),

  searchTerm: '',
  setSearchTerm: (searchTerm) => set({ searchTerm }),
}));
