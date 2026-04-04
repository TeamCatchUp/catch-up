import { cn } from '@/shared/utils/cn';

import { CATEGORY_LABEL, RESOURCE_LABEL } from '../../constants/auditLogConfig';
import type { AuditIntegrationLog } from '../../types/auditIntegrationLog';
import { formatDate } from '../../utils/formatDate';
import { getServiceIconCls, InfoRow, ResourceIcon, SERVICE_NAMES, ServiceIcon, StatusBadgeRow } from './helpers';

/** 동기화/연동 상세 패널 */
const SyncIntegrationDetail = ({ log }: { log: AuditIntegrationLog }) => {
  const iconCls = getServiceIconCls(log.service);

  return (
    <div className="flex h-full flex-col gap-4">
      {/* 서비스 아이콘 + 이름 */}
      <div className="flex items-center gap-3">
        <ServiceIcon service={log.service} className={iconCls} />
        <span className="text-heading-medium text-content-normal truncate">{SERVICE_NAMES[log.service]}</span>
      </div>

      <div className="flex flex-col gap-9">
        {/* 기본 정보 */}
        <div className="flex flex-col gap-2">
          <InfoRow label="일자" value={formatDate(log.executedAt)} />
          <InfoRow label="구분" value={CATEGORY_LABEL[log.category]} />
          <StatusBadgeRow status={log.status} />
        </div>

        {/* 연동된 데이터 범위 + 리소스 */}
        <div className="flex flex-col gap-5">
          {/* 연동된 데이터 범위 */}
          {log.dataRange && (
            <div className="flex flex-col gap-2">
              <h3 className="text-heading-small text-content-neutral">연동된 데이터 범위</h3>
              <div className="bg-fill-strong border-edge-assistive rounded-xl border px-5 py-2.5">
                <span className="text-body-small text-content-normal">{log.dataRange}</span>
              </div>
            </div>
          )}

          {/* 연동된 리소스 목록 */}
          {log.resources && log.resources.length > 0 && (
            <div className="flex flex-col gap-2">
              <h3 className="text-heading-small text-content-neutral">{RESOURCE_LABEL[log.service]}</h3>
              <div className="bg-fill-strong border-edge-assistive flex max-h-80 flex-col overflow-y-auto rounded-xl border">
                {log.resources.map((name, idx) => (
                  <div
                    key={name}
                    className={cn(
                      'border-edge-assistive flex h-13 shrink-0 items-center gap-3 px-4',
                      idx !== log.resources!.length - 1 && 'border-b',
                    )}
                  >
                    <div className="border-edge-neutral bg-fill-normal/50 flex items-center justify-center overflow-clip rounded-full border p-1.5">
                      <ResourceIcon service={log.service} />
                    </div>
                    <span className="text-body-small text-content-normal min-w-0 flex-1 truncate">{name}</span>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

export default SyncIntegrationDetail;
