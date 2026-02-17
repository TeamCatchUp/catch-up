import IconFilter from '@/public/icons/icon/filter-3.svg';
import { Button } from '@/shared/components/ui/button';

import type { MemberIntegrationRow } from '../../types/integrations';
import type { MemberDisplayRow } from '../../types/memberDisplay';
import MemberUserDetailPanel from './MemberUserDetailPanel';
import MemberUsersTable from './MemberUsersTable';

interface MemberUsersStatusSectionProps {
  rowCount: number;
  displayRows: MemberDisplayRow[];
  activeRenderKey: string | null;
  onSelectRenderKey: (renderKey: string) => void;
  selectedRow: MemberIntegrationRow | null;
}

/** 이용자 계정 연동 상태 섹션 */
const MemberUsersStatusSection = ({
  rowCount,
  displayRows,
  activeRenderKey,
  onSelectRenderKey,
  selectedRow,
}: MemberUsersStatusSectionProps) => {
  return (
    <section className="flex w-250 flex-col gap-3">
      <div className="flex items-end justify-between">
        <div className="flex flex-col gap-0.5">
          <h2 className="text-heading-large text-gray-80">
            이용자 계정 연동 상태 <span className="text-blue-40">{rowCount}</span>
          </h2>
          <p className="text-body-small text-gray-50">신규 회원의 가입 요청을 확인하고 승인하세요.</p>
        </div>

        <div className="flex items-center gap-2.5">
          <Button variant="box-outline-gray" size="md" className="text-body-small h-9">
            CSV 일괄등록
          </Button>
          <Button variant="icon-outline-gray" size="md" className="size-9 p-1.5">
            <IconFilter className="size-6" />
          </Button>
        </div>
      </div>

      <div className="border-neutral-3 grid h-124 min-h-0 w-250 grid-cols-[500px_500px] overflow-clip border-y">
        <MemberUsersTable
          displayRows={displayRows}
          activeRenderKey={activeRenderKey}
          onSelectRenderKey={onSelectRenderKey}
        />
        <MemberUserDetailPanel selectedRow={selectedRow} />
      </div>
    </section>
  );
};

export default MemberUsersStatusSection;
