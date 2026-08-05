export type { IntegrationAccountMeta, IntegrationService } from '@/shared/types/integrationService';

import type { IntegrationAccountMeta, IntegrationService } from '@/shared/types/integrationService';

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
   * 사이드바는 "{도구명} - {이 값}", 상세 헤더는 이 값만 쓴다.
   * 미연동이거나 백엔드가 null을 주면 null.
   */
  workspaceName: string | null;
}

/** 연동된 리소스 항목 (per-target 임베딩 기간 포함) */
export interface ConnectorResource {
  /** target 고유 키 — 대상 이름은 중복될 수 있어 목록 key로 쓰지 않는다 */
  id: string;
  name: string;
  dateRange: string | null;
  /**
   * 채널톡 전용 — 채널 아래 도큐먼트 스페이스.
   * 다른 도구는 계층이 없어 비워 둔다.
   */
  children?: ConnectorResource[];
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

