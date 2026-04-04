import Image from 'next/image';

import IconCloudCheckFilled from '@/public/icons/icon/cloud_check_filled.svg';
import DefaultProfile from '@/public/icons/icon/default_profile.svg';
import { cn } from '@/shared/utils/cn';

import { INTEGRATION_ACCOUNTS } from '../../../constants/integrations';
import type { MemberIntegrationRow } from '../../../types/integrations';

interface UserDetailPanelProps {
  selectedRow: MemberIntegrationRow | null;
}

/** 이용자 연동 우측 상세 패널 */
const UserDetailPanel = ({ selectedRow }: UserDetailPanelProps) => {
  if (!selectedRow) {
    return (
      <section className="bg-fill-normal overflow-clip pt-5 pb-5 pl-6">
        <div className="text-body-small text-content-alternative flex h-full items-center justify-center text-center">
          선택된 이용자 정보가 없습니다.
        </div>
      </section>
    );
  }

  return (
    <section className="bg-fill-normal overflow-clip pt-5 pb-5 pl-6">
      <div className="flex h-full flex-col gap-4">
        <div className="flex min-w-0 flex-1 items-center gap-3">
          <DefaultProfile className="text-content-assistive size-7 shrink-0 rounded-full" />
          <span className="text-heading-medium text-content-normal truncate">{selectedRow.userName}</span>
        </div>

        <div className="flex flex-col gap-9">
          <div className="text-body-small flex flex-col gap-2">
            <div className="flex w-full items-center gap-14">
              <span className="text-content-alternative w-19.75 shrink-0">메일</span>
              <span className="text-content-neutral min-w-0 flex-1 truncate">{selectedRow.email}</span>
            </div>
          </div>

          <div className="flex flex-col gap-2">
            <div className="flex items-center gap-2">
              <IconCloudCheckFilled className="text-content-assistive size-6" />
              <h3 className="text-heading-small text-content-neutral">연동된 계정 정보</h3>
            </div>

            <div className="border-edge-assistive flex h-63 w-119 flex-col overflow-clip rounded-xl border">
              {INTEGRATION_ACCOUNTS.map((account, index) => {
                const info = selectedRow.serviceInfoByService[account.service];
                const iconClassName = account.service === 'confluence' ? 'h-5.75 w-6 shrink-0' : 'h-6 w-6 shrink-0';

                return (
                  <div
                    key={`${selectedRow.userKey}-${account.service}`}
                    className={cn(
                      'border-edge-assistive flex h-15.75 w-119 shrink-0 items-center gap-5 overflow-clip px-4',
                      index !== INTEGRATION_ACCOUNTS.length - 1 && 'border-b',
                    )}
                  >
                    <div className="flex w-41.25 shrink-0 items-center gap-3">
                      <account.Icon className={iconClassName} />
                      <span className="text-body-small text-content-normal truncate">{account.name}</span>
                    </div>

                    <div className="flex shrink-0 flex-col items-start justify-center gap-0.5">
                      <div className="flex shrink-0 items-center gap-2.5">
                        {info?.picture ? (
                          <Image
                            src={info.picture}
                            alt=""
                            width={25}
                            height={25}
                            className="size-6.25 shrink-0 rounded-full"
                          />
                        ) : (
                          <DefaultProfile className="text-content-assistive size-6.25 shrink-0 rounded-full" />
                        )}
                        <span className="text-body-xsmall text-content-normal max-w-33.25 shrink-0 truncate">
                          {info?.name ?? '-'}
                        </span>
                        <span className="rounded-md2 bg-fill-interaction-hover text-body-xsmall text-content-alternative shrink-0 px-1.5 py-0.5">
                          {info?.identifier ?? '-'}
                        </span>
                      </div>
                      <span className="text-body-xsmall text-content-alternative shrink-0 truncate">
                        {selectedRow.email}
                      </span>
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        </div>
      </div>
    </section>
  );
};

export default UserDetailPanel;
