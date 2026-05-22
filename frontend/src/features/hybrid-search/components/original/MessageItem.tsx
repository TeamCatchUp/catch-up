'use client';

// 채팅 타임라인의 한 메시지. visibility + author.type 으로 변형.
// 배경 채움은 visibility === 'internal' 일 때만 — public 메시지는 배경 없음.

import Image from 'next/image';

import ContentRenderer from '@/features/hybrid-search/components/original/contents/ContentRenderer';
import type { OriginalMessageItem } from '@/features/hybrid-search/types/originalApi';
import FaceManIcon from '@/public/icons/icon/face_man.svg';
import HeadphoneIcon from '@/public/icons/icon/headphone.svg';
import LockIcon from '@/public/icons/icon/lock.svg';
import SupportAgentIcon from '@/public/icons/icon/support_agent.svg';

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
  const isCustomer = item.author?.type === 'customer';
  const isManager = item.author?.type === 'manager';
  const authorName = item.author?.name?.trim();
  const avatarUrl = item.author?.avatar_url ?? null;
  const timestamp = item.created_at ? formatTimestamp(item.created_at) : '';

  // 아바타 아이콘 — 문의자는 face_man, 상담원/내부는 support_agent
  const AvatarIcon = isCustomer ? FaceManIcon : SupportAgentIcon;

  return (
    <div
      className={`flex w-full gap-3 rounded-xl px-3 py-3 ${
        isInternal ? 'bg-accent-red-orange-lighten' : ''
      }`}
    >
      {/* 아바타 — avatar_url 부재 시 author.type 별 기본 아이콘 */}
      <div
        className={`flex size-8 shrink-0 items-center justify-center overflow-hidden rounded-lg ${
          isCustomer ? 'bg-accent-light-blue' : 'bg-accent-red-orange'
        }`}
      >
        {avatarUrl ? (
          <Image src={avatarUrl} alt="" width={32} height={32} className="size-8 object-cover" />
        ) : (
          <AvatarIcon aria-hidden className="text-icon-inverse size-6" />
        )}
      </div>

      <div className="flex min-w-0 flex-1 flex-col gap-1">
        {/* 작성자 행 — 이름 / 상담원 아이콘 / 내부 대화 태그 / 작성 시각 */}
        <div className="flex items-center gap-1.5">
          <span className="text-body-small text-content-normal truncate font-medium">
            {authorName ?? <span className="text-content-assistive">없음</span>}
          </span>
          {isManager && (
            <HeadphoneIcon aria-hidden className="text-accent-green size-4.5 shrink-0" />
          )}
          {isInternal && (
            <span className="bg-fill-interaction-hover text-content-alternative text-body-xsmall rounded-md2 flex shrink-0 items-center gap-1 px-1.5 py-0.5 font-medium">
              <LockIcon aria-hidden className="size-4.5" />
              내부 대화
            </span>
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
