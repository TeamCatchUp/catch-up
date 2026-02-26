'use client';

import { useUserStore } from '@/shared/store/userStore';

import AdminIntegrationsView from '../view/AdminIntegrationsView';
import UserIntegrationsView from '../view/UserIntegrationsView';

/** 권한에 따라 마이페이지 협업툴 연동 화면을 분기 렌더링 */
const IntegrationsPageClient = () => {
  const role = useUserStore((state) => state.user?.role);
  const isAdmin = role === 'admin';

  return isAdmin ? <AdminIntegrationsView /> : <UserIntegrationsView />;
};

export default IntegrationsPageClient;
