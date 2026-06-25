'use client';

import Link from 'next/link';

import ChatIcon from '@/public/icons/icon/chat.svg';

import type { HistoryGroup, HistoryItem } from '../types/historyModel';

/** {@link HistoryListItem} 컴포넌트 Props */
interface HistoryListItemProps {
  /** 렌더링할 히스토리 아이템 데이터 */
  item: HistoryItem;
  /** 아이템이 속한 날짜 그룹 (날짜 표시 형식 결정에 사용) */
  group: HistoryGroup;
}

/**
 * 히스토리 목록의 개별 아이템 행 컴포넌트.
 * 채팅 아이콘, 질문 텍스트, 저장 라벨, 날짜를 표시하며
 * 클릭 시 해당 채팅 세션으로 이동한다.
 */
export default function HistoryListItem({ item, group }: HistoryListItemProps) {
  const showSavedLabel = item.isSaved;
  const dateText = group === 'older' ? item.fullDate : item.relativeDate;

  return (
    <Link
      href={`/mypage/history/${item.sessionId}?q=${encodeURIComponent(item.query)}`}
      className="hover:bg-fill-normal-interaction-hover flex h-10 w-full items-center gap-2 rounded-xl px-2 py-1 transition-colors"
    >
      <div className="border-line-normal-neutral bg-fill-normal-strong rounded-rounded flex shrink-0 items-center justify-center border p-1.5">
        <ChatIcon className="text-text-normal-alternative size-5" />
      </div>
      <div className="text-body-small text-text-normal-normal min-w-0 flex-1 truncate text-left">{item.query}</div>
      <div className="text-body-xsmall text-text-normal-assistive flex shrink-0 items-center gap-2 whitespace-nowrap">
        {showSavedLabel && <span>저장한 답변</span>}
        <span>{dateText}</span>
      </div>
    </Link>
  );
}
