import { createElement } from 'react';

import IconCheckCircle from '@/public/icons/icon/check_circle.svg';
import IconDelete2 from '@/public/icons/icon/delete_2.svg';
import IconSpace from '@/public/icons/icon/space.svg';
import IconTag from '@/public/icons/icon/tag.svg';
import { INTEGRATION_ACCOUNTS } from '@/shared/constants/integrationAccounts';
import type { IntegrationService } from '@/shared/types/integrationService';
import { cn } from '@/shared/utils/cn';

import { STATUS_BADGE_CLASS, STATUS_LABEL } from '../../constants/auditLogConfig';

/** 서비스 → 아이콘 컴포넌트 (module-level stable reference) */
export const SERVICE_ICONS = Object.fromEntries(INTEGRATION_ACCOUNTS.map((a) => [a.service, a.Icon])) as Record<
  IntegrationService,
  (typeof INTEGRATION_ACCOUNTS)[number]['Icon']
>;

/** 서비스 → 이름 */
export const SERVICE_NAMES = Object.fromEntries(INTEGRATION_ACCOUNTS.map((a) => [a.service, a.name])) as Record<
  IntegrationService,
  string
>;

/** 서비스 아이콘 렌더러 (createElement 사용으로 react-hooks/static-components 회피) */
export const ServiceIcon = ({ service, className }: { service: IntegrationService; className?: string }) =>
  createElement(SERVICE_ICONS[service], { className });

/** 서비스 아이콘 className */
export const getServiceIconCls = (service: IntegrationService) =>
  service === 'confluence' ? 'h-5.75 w-6 shrink-0' : 'size-6 shrink-0';

/** 리소스 아이콘: Jira/Confluence → space, Slack → tag, Github → 서비스 아이콘 */
export const ResourceIcon = ({ service }: { service: IntegrationService }) => {
  if (service === 'slack') return <IconTag className="size-6 text-gray-50" />;
  if (service === 'github') return <ServiceIcon service="github" className="size-6" />;
  return <IconSpace className="size-6 text-gray-50" />;
};

/** 정보 행 */
export const InfoRow = ({ label, value }: { label: string; value: string }) => (
  <div className="text-body-small flex w-full items-center gap-14">
    <span className="w-19.75 shrink-0 text-gray-50">{label}</span>
    <span className="text-gray-70 min-w-0 flex-1 truncate">{value}</span>
  </div>
);

/** 상태 배지 InfoRow */
export const StatusBadgeRow = ({ status }: { status: 'success' | 'failure' }) => {
  const statusLabel = STATUS_LABEL[status];
  const badgeCls = STATUS_BADGE_CLASS[statusLabel] ?? 'bg-neutral-2 text-gray-50';
  const isSuccess = status === 'success';

  return (
    <div className="text-body-small flex w-full items-center gap-14">
      <span className="w-19.75 shrink-0 text-gray-50">상태</span>
      <span
        className={cn('rounded-md2 text-body-xsmall inline-flex shrink-0 items-center gap-1 px-1.5 py-0.5', badgeCls)}
      >
        {isSuccess ? <IconCheckCircle className="size-4" /> : <IconDelete2 className="size-4" />}
        {statusLabel}
      </span>
    </div>
  );
};
