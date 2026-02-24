import IconCloudCheckFilled from '@/public/icons/icon/cloud_check_filled.svg';
import IconCloudOff from '@/public/icons/icon/cloud_off.svg';
import DefaultProfile from '@/public/icons/icon/default_profile.svg';
import { INTEGRATION_ACCOUNTS } from '@/shared/constants/integrationAccounts';
import type { IntegrationService } from '@/shared/types/integrationService';
import { cn } from '@/shared/utils/cn';

import type { AuditLog } from '../../types/auditLog';
import { formatDate } from '../../utils/formatDate';

/** 정보 행 */
const InfoRow = ({ label, value }: { label: string; value: string }) => (
  <div className="flex w-full items-center gap-14">
    <span className="w-19.75 shrink-0 text-gray-50">{label}</span>
    <span className="text-gray-70 min-w-0 flex-1 truncate">{value}</span>
  </div>
);

/** 연동된 계정 정보 섹션 */
const IntegrationAccountsSection = ({
  name,
  email,
  accountIds,
}: {
  name: string;
  email: string;
  accountIds: Partial<Record<IntegrationService, string>>;
}) => (
  <div className="flex flex-col gap-2">
    <div className="flex items-center gap-2">
      <IconCloudCheckFilled className="text-gray-20 size-5" />
      <h3 className="text-heading-small text-gray-70">연동된 계정 정보</h3>
    </div>

    <div className="border-neutral-2 flex flex-col overflow-clip rounded-xl border">
      {INTEGRATION_ACCOUNTS.map((account, index) => {
        const accountId = accountIds[account.service];
        const isLinked = !!accountId;
        const iconClassName = account.service === 'confluence' ? 'h-5.75 w-6 shrink-0' : 'h-6 w-6 shrink-0';

        return (
          <div
            key={account.service}
            className={cn(
              'border-neutral-2 flex h-15.75 shrink-0 items-center gap-5 overflow-clip px-4 py-2',
              index !== INTEGRATION_ACCOUNTS.length - 1 && 'border-b',
            )}
          >
            <div className="flex w-41.25 shrink-0 items-center gap-3">
              <account.Icon className={iconClassName} />
              <span className="text-body-small text-gray-80 truncate">{account.name}</span>
            </div>

            {isLinked ? (
              <div className="flex shrink-0 flex-col items-start justify-center gap-0.5">
                <div className="flex shrink-0 items-center gap-2.5">
                  <DefaultProfile className="border-neutral-2 text-gray-30 size-6.25 shrink-0 rounded-full border" />
                  <span className="text-body-xsmall text-gray-80 max-w-33.25 shrink-0 truncate">{name}</span>
                  <span className="rounded-md2 bg-neutral-2 text-body-xsmall shrink-0 px-1.5 py-0.5 tracking-tight text-gray-50">
                    {accountId}
                  </span>
                </div>
                <span className="text-body-xsmall shrink-0 truncate text-gray-50">{email}</span>
              </div>
            ) : (
              <div className="bg-neutral-1 flex w-[259px] shrink-0 items-center justify-center self-stretch rounded-lg">
                <div className="flex items-center gap-1">
                  <IconCloudOff className="size-6 text-gray-50" />
                  <span className="text-body-xsmall text-gray-50">연동 안됨</span>
                </div>
              </div>
            )}
          </div>
        );
      })}
    </div>
  </div>
);

/** 계정관리 상세 패널 */
const AccountDetailPanel = ({ log }: { log: AuditLog }) => (
  <div className="flex h-full flex-col gap-4">
    {/* 프로필 + 이름 */}
    <div className="flex items-center gap-3">
      <DefaultProfile className="border-neutral-2 text-gray-30 size-7 shrink-0 rounded-full border" />
      <span className="text-heading-medium text-gray-80 truncate">{log.name}</span>
    </div>

    <div className="flex flex-col gap-9">
      {/* 기본 정보 */}
      <div className="text-body-small flex flex-col gap-2 tracking-tight">
        <InfoRow label="메일" value={log.email} />
        <InfoRow label="부서" value={log.department} />
        <InfoRow label="직급" value={log.rank} />
        <InfoRow label="가입일" value={formatDate(log.joinedAt)} />
        <InfoRow label="승인자" value={log.approver} />
      </div>

      {/* 연동된 계정 정보 */}
      <IntegrationAccountsSection name={log.name} email={log.email} accountIds={log.accountIds} />
    </div>
  </div>
);

export default AccountDetailPanel;
