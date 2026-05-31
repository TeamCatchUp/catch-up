import DateIndicator from '@/features/hybrid-search/components/original/shared/DateIndicator';
import type { SlackOriginalContentResponse } from '@/features/hybrid-search/types/slackOriginalApi';
import { parseSlackOriginalThread } from '@/features/hybrid-search/utils/slackOriginal/parseSlackOriginal';

import SlackMessageItem from './SlackMessageItem';
import SlackThreadHeader from './SlackThreadHeader';

interface SlackOriginalPanelPreviewProps {
  response: SlackOriginalContentResponse;
}

export default function SlackOriginalPanelPreview({ response }: SlackOriginalPanelPreviewProps) {
  const thread = parseSlackOriginalThread(response);
  const [parent, ...replies] = thread.messages;

  return (
    <div className="border-edge-normal flex w-105.75 max-w-full flex-col items-start justify-center gap-3 border-l py-4 pl-6">
      <SlackThreadHeader channelName={thread.channelName} participantNames={thread.participantNames} />
      <div className="custom-scrollbar flex w-99.75 max-w-full flex-col items-start gap-5 overflow-y-auto pb-5">
        {parent?.dateKey && <DateIndicator date={parent.dateKey} />}
        {parent && <SlackMessageItem message={parent} />}
        <div className="flex h-5 w-full items-center gap-3 px-3">
          <span className="text-body-xsmall text-content-alternative shrink-0 font-medium">
            {thread.commentCount}개의 댓글
          </span>
          <span aria-hidden className="bg-edge-neutral h-px min-w-0 flex-1" />
        </div>
        {replies.map((message) => (
          <SlackMessageItem key={message.id} message={message} />
        ))}
      </div>
    </div>
  );
}
