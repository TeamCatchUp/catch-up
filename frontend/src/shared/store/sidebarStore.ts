import { create } from 'zustand';

type PanelType = 'inbox' | 'settings' | 'questionsHistory' | null;

interface SidebarState {
  activePanel: PanelType;
  isSidebarOpen: boolean;
  lastSettingsPath: string;
  setActivePanel: (panel: PanelType) => void;
  setSidebarOpen: (isOpen: boolean) => void;
  setLastSettingsPath: (path: string) => void;
  togglePanel: (panel: 'inbox' | 'settings' | 'questionsHistory') => void;
}

export const useSidebarStore = create<SidebarState>((set) => ({
  activePanel: null,
  isSidebarOpen: true,
  lastSettingsPath: '/mypage/profile',
  setActivePanel: (panel) => set({ activePanel: panel }),
  setSidebarOpen: (isOpen) => set({ isSidebarOpen: isOpen }),
  setLastSettingsPath: (path) => set({ lastSettingsPath: path }),
  togglePanel: (panel) =>
    set((state) => ({
      activePanel: state.activePanel === panel ? null : panel,
    })),
}));
