import { create } from 'zustand';

interface SearchState {
  isModalOpen: boolean;
  searchQuery: string;
  filters: {
    tool: string[];
    assignee: string[];
    project: string[];
  };
  setModalOpen: (open: boolean) => void;
  setSearchQuery: (query: string) => void;
  setFilters: (filters: Partial<SearchState['filters']>) => void;
}

export const useSearchStore = create<SearchState>((set) => ({
  isModalOpen: false,
  searchQuery: '',
  filters: { tool: [], assignee: [], project: [] },
  setModalOpen: (open) => set({ isModalOpen: open }),
  setSearchQuery: (query) => set({ searchQuery: query }),
  setFilters: (newFilters) => set((state) => ({ filters: { ...state.filters, ...newFilters } })),
}));
