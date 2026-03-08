import type { ReactNode } from 'react';

import IconCloudCheckFilled from '@/public/icons/icon/cloud_check_filled.svg';
import IconCloudOff from '@/public/icons/icon/cloud_off.svg';
import DefaultProfile from '@/public/icons/icon/default_profile.svg';
import { INTEGRATION_ACCOUNTS } from '@/shared/constants/integrationAccounts';
import type { IntegrationService } from '@/shared/types/integrationService';
import { cn } from '@/shared/utils/cn';

import type { UserIntegrations } from '../../types/adminMember';

interface MemberDetailPanelProps {
  member: {
    name: string;
    email: string;
    department: string;
    rank: string;
    /** 상세 API 기반 연동 정보 (UserListSection) */
    integrations?: UserIntegrations;
    /** 레거시: 입장 신청 기반 계정 ID (EntryRequestSection) */
    accountIds?: Partial<Record<IntegrationService, string>>;
  } | null;
  actionButtons: ReactNode;
}

/** 연동 계정이 유효한지 확인 (null 또는 빈 객체면 false) */
const isValidAccount = (account: unknown): boolean => {
  if (!account || typeof account !== 'object') return false;
  return Object.keys(account).length > 0;
};

/** 서비스별 고유 식별자 추출 */
const getAccountIdentifier = (service: IntegrationService, integrations: UserIntegrations): string | null => {
  const account = integrations[service];
  if (!isValidAccount(account)) return null;
  switch (service) {
    case 'jira':
    case 'confluence':
      return (account as { accountId?: string }).accountId ?? null;
    case 'github':
      return (account as { login?: string }).login ?? null;
    case 'slack':
      return (account as { userId?: string }).userId ?? null;
  }
};

/** 우측 상세 패널 (입장 신청 / 이용자 목록 공통) */
const MemberDetailPanel = ({ member, actionButtons }: MemberDetailPanelProps) => {
  if (!member) {
    return (
      <section className="overflow-clip bg-fill-normal pt-5 pb-5 pl-6">
        <div className="text-body-small flex h-full items-center justify-center text-center text-content-alternative">
          선택된 이용자 정보가 없습니다.
        </div>
      </section>
    );
  }

  // integrations 모드: null/빈 객체인 서비스는 제외
  const visibleAccounts = member.integrations
    ? INTEGRATION_ACCOUNTS.filter((a) => isValidAccount(member.integrations![a.service]))
    : INTEGRATION_ACCOUNTS;

  return (
    <section className="overflow-clip bg-fill-normal pt-5 pb-5 pl-6">
      <div className="flex h-full flex-col gap-4">
        {/* 프로필 + 이름 + 액션 버튼 */}
        <div className="flex items-center justify-between pr-5">
          <div className="flex min-w-0 flex-1 items-center gap-3">
            <DefaultProfile className="border-edge-assistive text-content-assistive size-7 shrink-0 rounded-full border" />
            <span className="text-heading-medium text-content-normal truncate">{member.name}</span>
          </div>
          <div className="flex shrink-0 items-center gap-2.5">{actionButtons}</div>
        </div>

        <div className="flex flex-col gap-9">
          {/* 기본 정보 */}
          <div className="text-body-small flex flex-col gap-2 tracking-tight">
            <div className="flex w-full items-center gap-14">
              <span className="w-19.75 shrink-0 text-content-alternative">메일</span>
              <span className="text-content-neutral min-w-0 flex-1 truncate">{member.email}</span>
            </div>
            <div className="flex w-full items-center gap-14">
              <span className="w-19.75 shrink-0 text-content-alternative">부서</span>
              <span className="text-content-neutral min-w-0 flex-1 truncate">{member.department}</span>
            </div>
            <div className="flex w-full items-center gap-14">
              <span className="w-19.75 shrink-0 text-content-alternative">직급</span>
              <span className="text-content-neutral min-w-0 flex-1 truncate">{member.rank}</span>
            </div>
          </div>

          {/* 연동된 계정 정보 */}
          {visibleAccounts.length > 0 && (
            <div className="flex flex-col gap-2">
              <div className="flex items-center gap-2">
                <IconCloudCheckFilled className="text-content-assistive size-5" />
                <h3 className="text-heading-small text-content-neutral">연동된 계정 정보</h3>
              </div>

              <div className="border-edge-assistive flex w-119 flex-col overflow-clip rounded-xl border">
                {visibleAccounts.map((account, index) => {
                  // integrations 모드 vs legacy accountIds 모드
                  const accountId = member.integrations
                    ? getAccountIdentifier(account.service, member.integrations)
                    : (member.accountIds?.[account.service] ?? null);
                  const isLinked = !!accountId;

                  const integrationAccount = member.integrations?.[account.service];
                  const accountName =
                    integrationAccount && 'name' in integrationAccount ? integrationAccount.name : null;
                  const accountEmail =
                    integrationAccount && 'email' in integrationAccount ? integrationAccount.email : null;

                  const iconClassName = account.service === 'confluence' ? 'h-5.75 w-6 shrink-0' : 'h-6 w-6 shrink-0';

                  return (
                    <div
                      key={account.service}
                      className={cn(
                        'border-edge-assistive flex h-15.75 w-119 shrink-0 items-center gap-5 overflow-clip px-4 py-2',
                        index !== visibleAccounts.length - 1 && 'border-b',
                      )}
                    >
                      <div className="flex w-41.25 shrink-0 items-center gap-3">
                        <account.Icon className={iconClassName} />
                        <span className="text-body-small text-content-normal truncate">{account.name}</span>
                      </div>

                      {isLinked ? (
                        <div className="flex shrink-0 flex-col items-start justify-center gap-0.5">
                          <div className="flex shrink-0 items-center gap-2.5">
                            <DefaultProfile className="border-edge-assistive text-content-assistive size-6.25 shrink-0 rounded-full border" />
                            <span className="text-body-xsmall text-content-normal max-w-33.25 shrink-0 truncate">
                              {accountName ?? member.name}
                            </span>
                            <span className="rounded-md2 bg-fill-interaction-hover text-body-xsmall shrink-0 px-1.5 py-0.5 tracking-tight text-content-alternative">
                              {accountId}
                            </span>
                          </div>
                          <span className="text-body-xsmall shrink-0 truncate text-content-alternative">
                            {accountEmail ?? member.email}
                          </span>
                        </div>
                      ) : (
                        <div className="bg-fill-strong flex w-[259px] shrink-0 items-center justify-center self-stretch rounded-lg">
                          <div className="flex items-center gap-1">
                            <IconCloudOff className="text-content-assistive size-5" />
                            <span className="text-body-xsmall text-content-alternative">연동 안됨</span>
                          </div>
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>
            </div>
          )}
        </div>
      </div>
    </section>
  );
};

export default MemberDetailPanel;
