export type { IntegrationAccountMeta, IntegrationService } from '@/shared/types/integrationService';

import type { IntegrationAccountMeta, IntegrationService } from '@/shared/types/integrationService';

/** 관리자 연동 화면 탭 식별자 */
export type AdminIntegrationTab = 'my' | 'member';

/** 연동 계정 카드에 표시할 사용자 정보 */
export interface IntegrationAccountInfo {
  userName: string;
  userId: string;
  userEmail: string;
}

/** 관리자 좌측 연동 메뉴 아이템 */
export interface IntegrationMenuItem extends IntegrationAccountMeta {
  actionText: string;
  connected: boolean;
}

/** 관리자 연동 화면에서 사용하는 데이터 모델 */
export interface AdminIntegrationViewModel {
  integrationMenu: IntegrationMenuItem[];
  lastSyncedAt: string;
  spaceRows: string[];
}

/** 이용자 연동 상태 값 */
export type MemberIntegrationStatus = '미사용' | '완료' | '미등록';

/** 이용자 연동 탭의 사용자 행 데이터 */
export interface MemberIntegrationRow {
  userKey: string;
  userName: string;
  email: string;
  phone: string;
  department: string;
  teamSizeLabel: string;
  picture: string | null;
  accountIdByService: Partial<Record<IntegrationService, string>>;
  statusByService: Record<IntegrationService, MemberIntegrationStatus>;
}

/** 이용자 연동 탭 상단 카드 데이터 */
export interface MemberIntegrationCardItem extends IntegrationAccountMeta {
  completedCount: number;
  totalCount: number;
  completionRate: number;
}

/** 이용자 연동 탭 view model */
export interface MemberIntegrationViewModel {
  cards: MemberIntegrationCardItem[];
  rows: MemberIntegrationRow[];
}
