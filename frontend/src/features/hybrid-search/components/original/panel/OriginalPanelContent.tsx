// 원문 패널 본문 — 순수 조립 컴포넌트.
// 상담정보 → 고객정보 → (날짜 그룹별 DateIndicator + MessageItem) 메시지 영역.

import ConsultationInfo from '@/features/hybrid-search/components/original/metadata/ConsultationInfo';
import CustomerInfo from '@/features/hybrid-search/components/original/metadata/CustomerInfo';
import OriginalPanelEmpty from '@/features/hybrid-search/components/original/panel/states/OriginalPanelEmpty';
import DateIndicator from '@/features/hybrid-search/components/original/timeline/DateIndicator';
import MessageItem from '@/features/hybrid-search/components/original/timeline/MessageItem';
import type { OriginalContentResponse } from '@/features/hybrid-search/types/originalApi';
import { groupMessagesByDate } from '@/features/hybrid-search/utils/groupMessagesByDate';

interface OriginalPanelContentProps {
  data: OriginalContentResponse;
}

export default function OriginalPanelContent({ data }: OriginalPanelContentProps) {
  const dateGroups = groupMessagesByDate(data.items);

  return (
    <div className="flex h-full min-h-0 w-full flex-col gap-3 px-6 py-4">
      {/* 상담·고객 정보는 상단 고정 — 스크롤되지 않음 */}
      <ConsultationInfo metadata={data.metadata} />
      <CustomerInfo customer={data.metadata.customer} />

      {/* 메시지 영역만 내부 세로 스크롤 (custom-scrollbar 8px, overscroll-contain 으로 페이지 스크롤 전파 차단) */}
      {dateGroups.length > 0 ? (
        <div className="custom-scrollbar flex min-h-0 flex-1 flex-col gap-2 overflow-y-auto overscroll-contain pt-2">
          {dateGroups.map((group) => (
            <section key={group.date || 'undated'} className="flex flex-col gap-5">
              <DateIndicator date={group.date} />
              {group.items.map((item) => (
                <MessageItem
                  key={item.id}
                  item={item}
                  connector={data.connector}
                  documentId={data.document_id}
                />
              ))}
            </section>
          ))}
        </div>
      ) : (
        <OriginalPanelEmpty />
      )}
    </div>
  );
}
