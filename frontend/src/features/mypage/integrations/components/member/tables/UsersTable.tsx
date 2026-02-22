import DefaultProfile from '@/public/icons/icon/default_profile.svg';

import { MEMBER_TABLE_SERVICES } from '../../../constants/memberUi';
import type { MemberDisplayRow } from '../../../types/memberDisplay';

/** 서비스 키 → 테이블 헤더 레이블 */
const SERVICE_HEADER_LABELS: Record<string, string> = {
  github: 'Github',
  jira: 'Atlassian',
  slack: 'Slack',
};

interface UsersTableProps {
  displayRows: MemberDisplayRow[];
}

/** 이용자 연동 상태 테이블 */
const UsersTable = ({ displayRows }: UsersTableProps) => {
  return (
    <section className="flex h-full min-h-0 flex-col overflow-clip bg-white">
      <div className="border-neutral-3 bg-neutral-1 grid h-9 shrink-0 grid-cols-4 items-center border-b px-5">
        <span className="text-body-xsmall text-center text-gray-50">이름</span>
        {MEMBER_TABLE_SERVICES.map((service) => (
          <span key={service} className="text-body-xsmall text-center text-gray-50">
            {SERVICE_HEADER_LABELS[service] ?? service}
          </span>
        ))}
      </div>

      {displayRows.length === 0 ? (
        <div className="text-body-small flex h-full min-h-25 items-center justify-center px-4 text-center text-gray-50">
          표시할 이용자 연동 데이터가 없습니다.
        </div>
      ) : (
        <div className="flex min-h-0 flex-1 flex-col overflow-x-clip overflow-y-auto">
          {displayRows.map(({ renderKey, row }) => (
            <div
              key={renderKey}
              className="border-neutral-3 grid h-12.5 shrink-0 grid-cols-4 items-center border-b bg-white px-5"
            >
              <div className="flex items-center gap-4">
                <DefaultProfile className="border-neutral-2 text-gray-30 size-7 shrink-0 rounded-full border" />
                <span className="text-body-small text-gray-80 truncate">{row.userName}</span>
              </div>

              {MEMBER_TABLE_SERVICES.map((service) => (
                <span key={`${renderKey}-${service}`} className="text-body-small text-gray-60 truncate text-center">
                  {row.accountIdByService[service] ?? '-'}
                </span>
              ))}
            </div>
          ))}
        </div>
      )}
    </section>
  );
};

export default UsersTable;
