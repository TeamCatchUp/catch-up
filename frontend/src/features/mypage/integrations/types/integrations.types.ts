import type { ComponentType, SVGProps } from 'react';

/** 협업툴 서비스 식별자 */
export type IntegrationService = 'jira' | 'github' | 'slack' | 'confluence';

/** 관리자 연동 화면 탭 식별자 */
export type AdminIntegrationTab = 'my' | 'member';

/** 연동 계정 카드에 사용되는 기본 메타 정보 */
export interface IntegrationAccountMeta {
  service: IntegrationService;
  name: string;
  Icon: ComponentType<SVGProps<SVGSVGElement>>;
}

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
