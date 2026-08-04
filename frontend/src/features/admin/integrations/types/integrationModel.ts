export type { IntegrationAccountMeta, IntegrationService } from '@/shared/types/integrationService';

import type { IntegrationAccountMeta, IntegrationService } from '@/shared/types/integrationService';

import type { MappedSourceInfo } from './userSourceMappingApi';

/** 관리자 연동 화면 탭 식별자 */
export type AdminIntegrationTab = 'my' | 'member';

/** 커넥터 상세·메뉴 항목의 데이터 준비 상태 */
export type ConnectorDetailStatus = 'loading' | 'error' | 'ready';

/** 관리자 좌측 연동 메뉴 아이템 */
export interface IntegrationMenuItem extends IntegrationAccountMeta {
  actionText: string;
  connected: boolean;
  status: ConnectorDetailStatus;
  /**
   * 연동된 조직·워크스페이스의 대표 이름. connection-status `items[].name`이다.
   * 사이드바는 "{도구명} - {이 값}", 상세 헤더는 이 값만 쓴다(Figma `17125:115106`·`17071:111151`).
   * 미연동이거나 백엔드가 null을 주면 null.
   */
  workspaceName: string | null;
}

/** 연동된 리소스 항목 (per-target 임베딩 기간 포함) */
export interface ConnectorResource {
  name: string;
  dateRange: string | null;
}

/** 서비스별 연동 상세 정보 */
export interface ConnectorDetail {
  status: ConnectorDetailStatus;
  connected: boolean;
  dataRange: string;
  resources: ConnectorResource[];
  resourceLabel: string;
  /** 상세 헤더 제목에 쓰는 대표 이름 — {@link IntegrationMenuItem.workspaceName}과 같은 값 */
  workspaceName: string | null;
}

/** 관리자 연동 화면에서 사용하는 데이터 모델 */
export interface AdminIntegrationViewModel {
  integrationMenu: IntegrationMenuItem[];
  /** 선택된 서비스의 연동 상세 */
  getConnectorDetail: (service: IntegrationService) => ConnectorDetail;
}

/** 이용자 연동 상태 값 */
export type MemberIntegrationStatus = '미사용' | '완료' | '미등록';

/** 이용자 연동 탭의 사용자 행 데이터 */
export interface MemberIntegrationRow {
  /** React key + 행 식별자 (user_id 기반, 항상 존재) */
  userKey: string;
  /** OAuth sub — pre-mapping bulk update API의 sub 필드로 전송. null인 사용자는 매핑 수정 불가. */
  sub: string | null;
  userName: string;
  email: string;
  serviceInfoByService: Partial<Record<IntegrationService, MappedSourceInfo>>;
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
