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
  const dateText = group === 'sevenDays' ? item.relativeDate : item.fullDate;

  return (
    <Link
      href={`/admin/question-logs/${item.sessionId}?q=${encodeURIComponent(item.query)}&userId=${userId}`}
      className="hover:bg-neutral-2 flex h-10 w-full items-center gap-2 rounded-xl px-2 py-1 transition-colors"
    >
      <div className="border-neutral-3 bg-neutral-1 rounded-rounded flex shrink-0 items-center justify-center border p-1.5">
        <ChatIcon className="size-5 text-gray-50" />
      </div>
      <div className="text-body-small text-gray-80 min-w-0 flex-1 truncate text-left">{item.query}</div>
      {showDate && <span className="text-body-xsmall text-gray-30 shrink-0 whitespace-nowrap">{dateText}</span>}
    </Link>
  );
};

export default QuestionLogListItem;
