import type { ComponentType, SVGProps } from 'react';

/** 협업툴 서비스 식별자 (백엔드 SyncConnector enum과 동일 값) */
export type IntegrationService = 'jira' | 'github' | 'slack' | 'confluence' | 'channel_talk';

/** 연동 계정 카드에 사용되는 기본 메타 정보 */
export interface IntegrationAccountMeta {
  service: IntegrationService;
  name: string;
  Icon: ComponentType<SVGProps<SVGSVGElement>>;
}
