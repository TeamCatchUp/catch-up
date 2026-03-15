import Link from 'next/link';

import ChatIcon from '@/public/icons/icon/chat.svg';
import type { DateGroup } from '@/shared/utils/dateGrouping';

import type { QuestionLogItem } from '../types/questionLog';

interface QuestionLogListItemProps {
  item: QuestionLogItem;
  group: DateGroup;
  userId: string;
}

/** 질문 로그 리스트 행 */
const QuestionLogListItem = ({ item, group, userId }: QuestionLogListItemProps) => {
  const showDate = group !== 'today';
  const showSavedLabel = item.isSaved;
  const dateText = group === 'sevenDays' ? item.relativeDate : item.fullDate;

  return (
    <Link
      href={`/admin/question-logs/${item.messageId}?userId=${userId}`}
      className="hover:bg-fill-interaction-hover flex h-10 w-full items-center gap-2 rounded-xl px-2 py-1 transition-colors"
    >
      <div className="border-edge-neutral bg-fill-strong rounded-rounded flex shrink-0 items-center justify-center border p-1.5">
        <ChatIcon className="text-content-alternative size-5" />
      </div>
      <div className="text-body-small text-content-normal min-w-0 flex-1 truncate text-left">{item.query}</div>
      {(showSavedLabel || showDate) && (
        <div className="text-body-xsmall text-content-assistive flex shrink-0 items-center gap-2 whitespace-nowrap">
          {showSavedLabel && <span>저장한 답변</span>}
          {showDate && <span>{dateText}</span>}
        </div>
      )}
    </Link>
  );
};

export default QuestionLogListItem;
