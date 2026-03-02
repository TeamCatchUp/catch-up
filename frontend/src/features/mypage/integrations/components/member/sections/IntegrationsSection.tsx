import { useMemo } from 'react';

import { useMemberIntegrationViewModel } from '../../../hooks/useMemberIntegrationViewModel';
import { buildMemberDisplayRows } from '../../../utils/memberDisplay';
import StatusCardsSection from './StatusCardsSection';
import UsersStatusSection from './UsersStatusSection';

/** 관리자 이용자 연동 탭 섹션 (기존 API만 사용) */
const IntegrationsSection = () => {
  const { cards, rows } = useMemberIntegrationViewModel();

  const displayRows = useMemo(() => buildMemberDisplayRows(rows), [rows]);

  return (
    <section className="flex w-250 flex-col gap-10">
      <StatusCardsSection cards={cards} />
      <UsersStatusSection rowCount={rows.length} displayRows={displayRows} />
    </section>
  );
};

export default IntegrationsSection;
