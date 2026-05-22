// 원문 패널 본문 — 순수 조립 컴포넌트.
// 상담정보 → 고객정보 → (날짜 그룹별 DateIndicator + MessageItem) 메시지 영역.

import ConsultationInfo from '@/features/hybrid-search/components/original/ConsultationInfo';
import CustomerInfo from '@/features/hybrid-search/components/original/CustomerInfo';
import DateIndicator from '@/features/hybrid-search/components/original/DateIndicator';
import MessageItem from '@/features/hybrid-search/components/original/MessageItem';
import OriginalPanelEmpty from '@/features/hybrid-search/components/original/OriginalPanelEmpty';
import type { OriginalContentResponse } from '@/features/hybrid-search/types/originalApi';
import { groupMessagesByDate } from '@/features/hybrid-search/utils/groupMessagesByDate';

interface OriginalPanelContentProps {
  data: OriginalContentResponse;
}

export default function OriginalPanelContent({ data }: OriginalPanelContentProps) {
  const dateGroups = groupMessagesByDate(data.items);

  return (
    <div className="flex h-full min-h-0 w-full flex-col">
      {/* 상담·고객 정보 + 메시지 영역 — 함께 세로 스크롤 */}
      <div className="flex min-h-0 flex-1 flex-col gap-3 overflow-y-auto px-6 py-4">
        <ConsultationInfo metadata={data.metadata} />
        <CustomerInfo customer={data.metadata.customer} />

        {dateGroups.length > 0 ? (
          <div className="flex flex-col gap-2 pt-2">
            {dateGroups.map((group) => (
              <section key={group.date || 'undated'} className="flex flex-col gap-2">
                <DateIndicator date={group.date} />
                {group.items.map((item) => (
                  <MessageItem key={item.id} item={item} />
                ))}
              </section>
            ))}
          </div>
        ) : (
          <OriginalPanelEmpty />
        )}
      </div>
    </div>
  );
}
