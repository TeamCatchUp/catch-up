import { create } from 'zustand';

type PanelType = 'inbox' | 'settings' | 'questionsHistory' | null;

interface SidebarState {
  activePanel: PanelType;
  isSidebarOpen: boolean;
  isDocSearchOpen: boolean;
  lastSettingsPath: string;
  setActivePanel: (panel: PanelType) => void;
  setSidebarOpen: (isOpen: boolean) => void;
  setDocSearchOpen: (isOpen: boolean) => void;
  setLastSettingsPath: (path: string) => void;
  togglePanel: (panel: 'inbox' | 'settings' | 'questionsHistory') => void;
}

export const useSidebarStore = create<SidebarState>((set) => ({
  activePanel: null,
  isSidebarOpen: true,
  isDocSearchOpen: false,
  lastSettingsPath: '/mypage/profile',
  setActivePanel: (panel) => set({ activePanel: panel }),
  setSidebarOpen: (isOpen) => set({ isSidebarOpen: isOpen }),
  // 문서 탐색 모달은 패널과 달리 화면 위에 뜨므로 activePanel과 별개로 둔다.
  setDocSearchOpen: (isOpen) => set({ isDocSearchOpen: isOpen }),
  setLastSettingsPath: (path) => set({ lastSettingsPath: path }),
  togglePanel: (panel) =>
    set((state) => ({
      activePanel: state.activePanel === panel ? null : panel,
    })),
}));
