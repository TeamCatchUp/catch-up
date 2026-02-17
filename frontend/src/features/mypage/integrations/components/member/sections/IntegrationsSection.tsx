import { useMemo, useState } from 'react';

import { MEMBER_TABLE_SERVICES } from '../../../constants/memberUi';
import { useMemberIntegrationViewModel } from '../../../hooks/useMemberIntegrationViewModel';
import { buildMemberDisplayRows } from '../../../utils/memberDisplay';
import StatusCardsSection from './StatusCardsSection';
import UsersStatusSection from './UsersStatusSection';

/** 관리자 이용자 연동 탭 섹션 (기존 API만 사용) */
const IntegrationsSection = () => {
  const { cards, rows } = useMemberIntegrationViewModel();
  const [selectedRenderKey, setSelectedRenderKey] = useState<string | null>(null);

  const displayRows = useMemo(() => buildMemberDisplayRows(rows, MEMBER_TABLE_SERVICES), [rows]);

  const activeRenderKey = useMemo(() => {
    if (displayRows.length === 0) return null;
    if (selectedRenderKey && displayRows.some((displayRow) => displayRow.renderKey === selectedRenderKey)) {
      return selectedRenderKey;
    }
    return displayRows[0].renderKey;
  }, [displayRows, selectedRenderKey]);

  const selectedRow = useMemo(
    () => displayRows.find((displayRow) => displayRow.renderKey === activeRenderKey)?.row ?? null,
    [displayRows, activeRenderKey],
  );

  return (
    <section className="flex w-250 flex-col gap-10">
      <StatusCardsSection cards={cards} />
      <UsersStatusSection
        rowCount={rows.length}
        displayRows={displayRows}
        activeRenderKey={activeRenderKey}
        onSelectRenderKey={setSelectedRenderKey}
        selectedRow={selectedRow}
      />
    </section>
  );
};

export default IntegrationsSection;
