// ChannelTalk 원문 패널 본문 — 순수 조립 컴포넌트.
// 상담정보 → 고객정보 → (날짜 그룹별 DateIndicator + MessageItem) 메시지 영역.

import ConsultationInfo from '@/features/hybrid-search/components/original/channel-talk/metadata/ConsultationInfo';
import CustomerInfo from '@/features/hybrid-search/components/original/channel-talk/metadata/CustomerInfo';
import MessageItem from '@/features/hybrid-search/components/original/channel-talk/timeline/MessageItem';
import DateIndicator from '@/features/hybrid-search/components/original/shared/DateIndicator';
import OriginalPanelEmpty from '@/features/hybrid-search/components/original/shared/states/OriginalPanelEmpty';
import type { OriginalContentResponse } from '@/features/hybrid-search/types/originalApi';
import { groupMessagesByDate } from '@/features/hybrid-search/utils/groupMessagesByDate';

interface ChannelTalkOriginalPanelContentProps {
  data: OriginalContentResponse;
}

export default function ChannelTalkOriginalPanelContent({
  data,
}: ChannelTalkOriginalPanelContentProps) {
  const dateGroups = groupMessagesByDate(data.items);

  return (
    <div className="flex w-full flex-col gap-3 px-6 py-4">
      <ConsultationInfo metadata={data.metadata} />
      <CustomerInfo customer={data.metadata.customer} />

      {dateGroups.length > 0 ? (
        <div className="flex flex-col gap-2 pt-2">
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
