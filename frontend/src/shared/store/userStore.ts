import { create } from 'zustand';

import type { UserRole, UserStatus } from '@/shared/queries/auth.types';

interface User {
  name: string;
  email: string;
  picture?: string;
  role: UserRole;
  status: UserStatus;
}

interface UserStore {
  user: User | null;
  setUser: (user: User) => void;
  clearUser: () => void;
}

export const useUserStore = create<UserStore>((set) => ({
  user: null,
  setUser: (user) => set({ user }),
  clearUser: () => set({ user: null }),
}));
