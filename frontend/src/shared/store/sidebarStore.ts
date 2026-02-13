import { create } from 'zustand';

type PanelType = 'inbox' | 'settings' | 'questionsHistory' | null;

interface SidebarState {
  activePanel: PanelType;
  setActivePanel: (panel: PanelType) => void;
  togglePanel: (panel: 'inbox' | 'settings' | 'questionsHistory') => void;
}

export const useSidebarStore = create<SidebarState>((set) => ({
  activePanel: null,
  setActivePanel: (panel) => set({ activePanel: panel }),
  togglePanel: (panel) =>
    set((state) => ({
      activePanel: state.activePanel === panel ? null : panel,
    })),
}));
