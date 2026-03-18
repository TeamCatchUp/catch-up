export type { IntegrationAccountMeta, IntegrationService } from '@/shared/types/integrationService';

import type { IntegrationAccountMeta, IntegrationService } from '@/shared/types/integrationService';

import type { PreMappingInfo } from './api';

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

/** 연동된 리소스 항목 (per-target 임베딩 기간 포함) */
export interface ConnectorResource {
  name: string;
  dateRange: string | null;
}

/** 서비스별 연동 상세 정보 */
export interface ConnectorDetail {
  connected: boolean;
  dataRange: string;
  resources: ConnectorResource[];
  resourceLabel: string;
}

/** 관리자 연동 화면에서 사용하는 데이터 모델 */
export interface AdminIntegrationViewModel {
  integrationMenu: IntegrationMenuItem[];
  /** 선택된 서비스의 연동 상세 */
  getConnectorDetail: (service: IntegrationService) => ConnectorDetail;
  isLoading: boolean;
}

/** 이용자 연동 상태 값 */
export type MemberIntegrationStatus = '미사용' | '완료' | '미등록';

/** 이용자 연동 탭의 사용자 행 데이터 */
export interface MemberIntegrationRow {
  userKey: string;
  userName: string;
  email: string;
  serviceInfoByService: Partial<Record<IntegrationService, PreMappingInfo>>;
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
  total: number;
  isLoading: boolean;
}
