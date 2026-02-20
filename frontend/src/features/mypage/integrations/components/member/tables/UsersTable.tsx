import IconCheckCircle from '@/public/icons/icon/check_circle.svg';
import DefaultProfile from '@/public/icons/icon/default_profile.svg';
import IconError from '@/public/icons/icon/error.svg';
import { cn } from '@/shared/utils/cn';

import {
  getMemberStatusBadgeClassName,
  MEMBER_LIST_STATUS_BADGE_BASE_CLASS,
  MEMBER_TABLE_SERVICES,
} from '../../../constants/memberUi';
import type { MemberDisplayRow } from '../../../types/memberDisplay';

interface UsersTableProps {
  displayRows: MemberDisplayRow[];
  activeRenderKey: string | null;
  onSelectRenderKey: (renderKey: string) => void;
}

/** 이용자 연동 좌측 상태 테이블 */
const UsersTable = ({ displayRows, activeRenderKey, onSelectRenderKey }: UsersTableProps) => {
  return (
    <section className="border-neutral-3 flex h-full min-h-0 flex-col overflow-clip border-r bg-white">
      <div className="border-neutral-3 bg-neutral-1 grid h-9 shrink-0 grid-cols-4 items-center border-b px-5">
        <span className="text-body-xsmall text-center text-gray-50">이름</span>
        <span className="text-body-xsmall text-center text-gray-50">Github</span>
        <span className="text-body-xsmall text-center text-gray-50">Jira</span>
        <span className="text-body-xsmall text-center text-gray-50">Slack</span>
      </div>

      {displayRows.length === 0 ? (
        <div className="text-body-small flex h-full min-h-25 items-center justify-center px-4 text-center text-gray-50">
          표시할 이용자 연동 데이터가 없습니다.
        </div>
      ) : (
        <div className="flex min-h-0 flex-1 flex-col overflow-x-clip overflow-y-auto">
          {displayRows.map(({ renderKey, row, displayStatusByService }) => {
            const isSelected = activeRenderKey === renderKey;

            return (
              <button
                key={renderKey}
                type="button"
                onClick={() => onSelectRenderKey(renderKey)}
                className={cn(
                  'border-neutral-3 grid h-12.5 shrink-0 cursor-pointer grid-cols-4 items-center border-b px-5 text-left',
                  isSelected ? 'bg-blue-1' : 'hover:bg-neutral-1 bg-white',
                )}
              >
                <div className="flex items-center gap-4">
                  <DefaultProfile className="border-neutral-2 text-gray-30 size-7.5 shrink-0 rounded-full border" />
                  <span className="text-body-small text-gray-80 truncate">{row.userName}</span>
                </div>

                {MEMBER_TABLE_SERVICES.map((service) => (
                  <div key={`${renderKey}-${service}`} className="flex items-center justify-center">
                    <span
                      className={cn(
                        MEMBER_LIST_STATUS_BADGE_BASE_CLASS,
                        getMemberStatusBadgeClassName(displayStatusByService[service]),
                      )}
                    >
                      {displayStatusByService[service] === '완료' && <IconCheckCircle className="size-4" />}
                      {displayStatusByService[service] === '미등록' && <IconError className="size-4" />}
                      {displayStatusByService[service]}
                    </span>
                  </div>
                ))}
              </button>
            );
          })}
        </div>
      )}
    </section>
  );
};

export default UsersTable;
