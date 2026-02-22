import { create } from 'zustand';

import type { DatePeriod, SortOrder } from '@/shared/utils/dateGrouping';

interface QuestionLogFilterStore {
  selectedUserId: string;
  setSelectedUserId: (id: string) => void;

  sort: SortOrder;
  setSort: (sort: SortOrder) => void;

  period: DatePeriod;
  setPeriod: (period: DatePeriod) => void;

  savedOnly: boolean;
  toggleSavedOnly: () => void;

  searchTerm: string;
  setSearchTerm: (term: string) => void;
}

export const useQuestionLogFilterStore = create<QuestionLogFilterStore>((set) => ({
  selectedUserId: '',
  setSelectedUserId: (id) => set({ selectedUserId: id }),

  sort: 'latest',
  setSort: (sort) => set({ sort }),

  period: 'all',
  setPeriod: (period) => set({ period }),

  savedOnly: false,
  toggleSavedOnly: () => set((s) => ({ savedOnly: !s.savedOnly })),

  searchTerm: '',
  setSearchTerm: (term) => set({ searchTerm: term }),
}));
