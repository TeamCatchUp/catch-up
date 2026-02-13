import { create } from 'zustand';

type PanelType = 'inbox' | 'settings' | 'questionsHistory' | null;

interface SidebarState {
  activePanel: PanelType;
  isSidebarOpen: boolean;
  setActivePanel: (panel: PanelType) => void;
  setSidebarOpen: (isOpen: boolean) => void;
  togglePanel: (panel: 'inbox' | 'settings' | 'questionsHistory') => void;
}

export const useSidebarStore = create<SidebarState>((set) => ({
  activePanel: null,
  isSidebarOpen: true,
  setActivePanel: (panel) => set({ activePanel: panel }),
  setSidebarOpen: (isOpen) => set({ isSidebarOpen: isOpen }),
  togglePanel: (panel) =>
    set((state) => ({
      activePanel: state.activePanel === panel ? null : panel,
    })),
}));
