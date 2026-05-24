'use client';

// 채팅 타임라인의 한 메시지. visibility + author.type 으로 변형.
// Figma 14065-64692 (customer) / 14071-65320 (internal):
//   외부 row [bg, padding 0 10 0 0, gap 12]
//   ├─ stripe span (w 3px, vertical fill, self-stretch, rounded-full 양끝 cap)
//   └─ inner row [padding 4 0, gap 12]
//      ├─ avatar wrapper (size 32, radius 8, bg)
//      └─ col [gap 8]
//         ├─ author row (gap 6, 작성자명 #6D7882 + manager 아이콘 + 내부대화 Tag + timestamp)
//         └─ contents
// customer 가 우선 — customer 면 visibility 와 무관하게 customer 디자인.

import Image from 'next/image';

import ContentRenderer from '@/features/hybrid-search/components/original/contents/ContentRenderer';
import type { OriginalMessageItem } from '@/features/hybrid-search/types/originalApi';
import { formatTimestamp } from '@/features/hybrid-search/utils/format/formatTimestamp';
import FaceManIcon from '@/public/icons/icon/face_man.svg';
import HeadphoneIcon from '@/public/icons/icon/headphone.svg';
import LockIcon from '@/public/icons/icon/lock.svg';
import SupportAgentIcon from '@/public/icons/icon/support_agent.svg';
import { Badge } from '@/shared/components/ui/badge';
import type { SourceTypeApi } from '@/shared/types/sourceApi';

interface MessageItemProps {
  item: OriginalMessageItem;
  // FileRow 가 파일 다운로드 mutation 호출 시 필요 — 4단 prop drilling.
  connector: SourceTypeApi;
  documentId: string;
}

export default function MessageItem({ item, connector, documentId }: MessageItemProps) {
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
      className={`flex w-full gap-2.25 pr-2.5 ${
        isCustomer
          ? 'bg-fill-primary-assistive'
          : isInternal
            ? 'bg-accent-red-orange-lighten'
            : ''
      }`}
    >
      {/* Figma 14065-64693 — 좌측 stripe (3px, 양 끝 반원 cap). stripe 공간은 항상 차지(색만 conditional)
          하여 bg/stripe 없는 메시지도 동일 좌측 정렬 유지 — Figma 의 form 메시지가 stripe fills empty 인 것과 동일 패턴. */}
      <span
        aria-hidden
        className={`w-[3px] shrink-0 self-stretch rounded-full ${
          isCustomer
            ? 'bg-edge-primary-strong'
            : isInternal
              ? 'bg-accent-red-orange'
              : 'bg-transparent'
        }`}
      />

      {/* inner row — padding 4 0 (상하 4), gap 12 (아바타 ↔ col) */}
      <div className="flex min-w-0 flex-1 gap-3 py-1">
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

        {/* 우측 col — author row ↔ contents gap */}
        <div className="flex min-w-0 flex-1 flex-col gap-1">
          {/* 작성자 행 — 이름 / 상담원 아이콘 / 내부 대화 태그 / 작성 시각 */}
          <div className="flex items-center gap-1.5">
            <span className="text-body-small text-content-alternative truncate font-medium">
              {authorName ?? <span className="text-content-assistive">없음</span>}
            </span>
            {isManager && (
              <HeadphoneIcon aria-hidden className="text-accent-green size-4.5 shrink-0" />
            )}
            {isInternal && (
              <Badge
                variant="secondary"
                size="md"
                className="rounded-md2 shrink-0 gap-1 px-1.5 py-0.5 font-medium"
              >
                <LockIcon aria-hidden className="size-4.5" />
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
              <ContentRenderer
                key={`${content.content_type}-${index}`}
                content={content}
                connector={connector}
                documentId={documentId}
              />
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
