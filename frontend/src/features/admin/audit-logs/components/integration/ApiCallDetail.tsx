import { CATEGORY_LABEL } from '../../constants/auditLogConfig';
import type { AuditIntegrationLog } from '../../types/auditIntegrationLogModel';
import { formatDate } from '../../utils/formatDate';
import { getServiceIconCls, InfoRow, SERVICE_NAMES, ServiceIcon } from './Helpers';

/** API 호출 상세 패널 */
export default function ApiCallDetail({ log }: { log: AuditIntegrationLog }) {
  const iconCls = getServiceIconCls(log.service);

  return (
    <div className="flex h-full flex-col gap-4">
      {/* 서비스 아이콘 + 이름 */}
      <div className="flex items-center gap-3">
        <ServiceIcon service={log.service} className={iconCls} />
        <span className="text-heading-medium text-content-normal truncate">{SERVICE_NAMES[log.service]}</span>
      </div>

      <div className="flex flex-col gap-9">
        {/* 기본 정보 (상태 없음) */}
        <div className="flex flex-col gap-2">
          <InfoRow label="일자" value={formatDate(log.executedAt)} />
          <InfoRow label="구분" value={CATEGORY_LABEL[log.category]} />
        </div>

        {/* API 호출 사유 + 수신 데이터 */}
        <div className="flex flex-col gap-5">
          {/* API 호출 사유 */}
          {log.apiCallReason && (
            <div className="flex flex-col gap-2">
              <h3 className="text-heading-small text-content-neutral">API 호출 사유</h3>
              <div className="bg-fill-strong border-edge-assistive rounded-xl border px-5 py-2.5">
                <span className="text-body-small text-content-normal">{log.apiCallReason}</span>
              </div>
            </div>
          )}

          {/* 수신 데이터 */}
          {log.receivedData && (
            <div className="flex flex-col gap-2">
              <h3 className="text-heading-small text-content-neutral">수신 데이터</h3>
              <div className="bg-fill-strong border-edge-assistive max-h-80 overflow-y-auto rounded-xl border px-5 py-4">
                <pre className="text-label-small text-content-normal break-all whitespace-pre-wrap">
                  {log.receivedData}
                </pre>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
