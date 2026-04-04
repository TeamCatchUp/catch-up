import type { DateRange } from 'react-day-picker';
import { create } from 'zustand';

import type { AuditSortKey } from '../types/auditLogModel';

interface AuditQuestionFilterStore {
  sort: AuditSortKey;
  setSort: (sort: AuditSortKey) => void;

  dateRange: DateRange | undefined;
  setDateRange: (range: DateRange | undefined) => void;

  searchTerm: string;
  setSearchTerm: (term: string) => void;

  currentPage: number;
  setCurrentPage: (page: number) => void;
}

export const useAuditQuestionFilterStore = create<AuditQuestionFilterStore>((set) => ({
  sort: 'newest',
  setSort: (sort) => set({ sort, currentPage: 1 }),

  dateRange: undefined,
  setDateRange: (dateRange) => set({ dateRange, currentPage: 1 }),

  searchTerm: '',
  setSearchTerm: (searchTerm) => set({ searchTerm, currentPage: 1 }),

  currentPage: 1,
  setCurrentPage: (currentPage) => set({ currentPage }),
}));
