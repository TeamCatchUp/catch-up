import type { ComponentType, SVGProps } from 'react';

/** 협업툴 서비스 식별자 */
export type IntegrationService = 'jira' | 'github' | 'slack' | 'confluence' | 'channel-talk';

/** 연동 계정 카드에 사용되는 기본 메타 정보 */
export interface IntegrationAccountMeta {
  service: IntegrationService;
  name: string;
  Icon: ComponentType<SVGProps<SVGSVGElement>>;
}
