'use client';

// 채팅 타임라인의 한 메시지. visibility + author.type 으로 변형.
// 배경 채움은 visibility === 'internal' 일 때만 — public 메시지는 배경 없음.

import Image from 'next/image';

import ContentRenderer from '@/features/hybrid-search/components/original/contents/ContentRenderer';
import type { OriginalMessageItem } from '@/features/hybrid-search/types/originalApi';
import DefaultProfile from '@/public/icons/icon/default_profile.svg';
import HeadphoneIcon from '@/public/icons/icon/headphone.svg';
import LockIcon from '@/public/icons/icon/lock.svg';
import { Badge } from '@/shared/components/ui/badge';

interface MessageItemProps {
  item: OriginalMessageItem;
}

// ISO datetime → 02:33 PM. 파싱 불가하면 빈 문자열.
function formatTimestamp(value: string): string {
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return '';

  let hours = parsed.getHours();
  const minutes = String(parsed.getMinutes()).padStart(2, '0');
  const meridiem = hours >= 12 ? 'PM' : 'AM';
  hours %= 12;
  if (hours === 0) hours = 12;
  return `${String(hours).padStart(2, '0')}:${minutes} ${meridiem}`;
}

export default function MessageItem({ item }: MessageItemProps) {
  const isInternal = item.visibility === 'internal';
  const isManager = item.author?.type === 'manager';
  const authorName = item.author?.name?.trim();
  const avatarUrl = item.author?.avatar_url ?? null;
  const timestamp = item.created_at ? formatTimestamp(item.created_at) : '';

  return (
    <div
      className={`flex w-full gap-3 rounded-xl px-3 py-3 ${
        isInternal ? 'bg-accent-red-orange-lighten' : ''
      }`}
    >
      {/* 아바타 — avatar_url 부재 시 기본 프로필 아이콘 */}
      <div
        className={`flex size-8 shrink-0 items-center justify-center overflow-hidden rounded-full ${
          isManager ? 'bg-accent-red-orange' : 'bg-accent-light-blue'
        }`}
      >
        {avatarUrl ? (
          <Image src={avatarUrl} alt="" width={32} height={32} className="size-8 object-cover" />
        ) : (
          <DefaultProfile className="text-icon-inverse size-6" />
        )}
      </div>

      <div className="flex min-w-0 flex-1 flex-col gap-1.5">
        {/* 작성자 행 — 이름 / 상담원 아이콘 / 내부 대화 배지 / 작성 시각 */}
        <div className="flex items-center gap-2">
          <span className="text-body-small text-content-normal truncate font-medium">
            {authorName ?? <span className="text-content-assistive">없음</span>}
          </span>
          {isManager && (
            <HeadphoneIcon aria-hidden className="text-accent-red-orange size-4.5 shrink-0" />
          )}
          {isInternal && (
            <Badge variant="orange" size="sm" className="shrink-0 gap-1 px-1.5">
              <LockIcon aria-hidden className="size-3.5" />
              내부 대화
            </Badge>
          )}
          {timestamp && (
            <span className="text-body-xsmall text-content-assistive ml-auto shrink-0">
              {timestamp}
            </span>
          )}
        </div>

        {/* 본문 — contents[] 각 요소를 ContentRenderer 로 */}
        <div className="flex flex-col gap-2">
          {item.contents.map((content, index) => (
            <ContentRenderer key={index} content={content} />
          ))}
        </div>
      </div>
    </div>
  );
}
