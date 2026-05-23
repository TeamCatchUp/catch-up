'use client';

// 상담 정보 섹션 — 담당자(아바타+이름) / 상담 태그 / 상담 설명.
// 좌측 라벨 컬럼은 138px 고정, 우측 값과의 gap 은 40px.

import Image from 'next/image';

import type { OriginalMetadata } from '@/features/hybrid-search/types/originalApi';
import DefaultProfileIcon from '@/public/icons/icon/default_profile.svg';
import FileIcon from '@/public/icons/icon/file.svg';
import PersonFilledIcon from '@/public/icons/icon/person_filled.svg';
import TagIcon from '@/public/icons/icon/tag.svg';
import { Badge } from '@/shared/components/ui/badge';

interface ConsultationInfoProps {
  metadata: OriginalMetadata;
}

interface FieldLabelProps {
  icon: typeof TagIcon;
  text: string;
}

function FieldLabel({ icon: Icon, text }: FieldLabelProps) {
  return (
    <span className="flex w-[138px] shrink-0 items-center gap-4">
      <Icon className="text-icon-neutral h-5.5 w-5.5" />
      <span className="text-body-small text-content-alternative">{text}</span>
    </span>
  );
}

export default function ConsultationInfo({ metadata }: ConsultationInfoProps) {
  // 담당자 — 응답엔 assignee_id만 오므로 managers[]에서 이름·아바타를 조회.
  const assignment = metadata.assignment;
  const assigneeId = assignment?.assignee_id;
  const assignee = assigneeId
    ? assignment?.managers?.find((manager) => manager.manager_id === assigneeId)
    : undefined;
  const assigneeName = assignee?.name?.trim();
  const assigneeAvatar = assignee?.avatar_url?.trim() ? assignee.avatar_url : null;
  const description = metadata.description?.trim();
  const tagNames = (metadata.tags ?? [])
    .map((tag) => tag.name?.trim())
    .filter((name): name is string => Boolean(name));

  return (
    <section className="bg-fill-strong border-edge-neutral flex w-full flex-col gap-3 rounded-xl border px-5 py-4">
      <div className="flex items-center gap-10">
        <FieldLabel icon={PersonFilledIcon} text="담당자" />
        <div className="flex min-w-0 flex-1 items-center gap-2">
          {assigneeAvatar ? (
            <Image
              src={assigneeAvatar}
              alt=""
              width={25}
              height={25}
              className="size-6.25 shrink-0 rounded-full object-cover"
            />
          ) : (
            <DefaultProfileIcon aria-hidden className="size-6.25 shrink-0" />
          )}
          <span className="text-body-small text-content-neutral truncate">
            {assigneeName ?? <span className="text-content-assistive">없음</span>}
          </span>
        </div>
      </div>

      {tagNames.length > 0 ? (
        <div className="flex flex-col gap-2">
          <FieldLabel icon={TagIcon} text="상담 태그" />
          <div className="flex flex-wrap gap-x-1.5 gap-y-3">
            {tagNames.map((name, index) => (
              <Badge
                key={`${name}-${index}`}
                variant="default"
                size="md"
                className="rounded-md2 px-1.5 py-0.5 font-medium"
              >
                {name}
              </Badge>
            ))}
          </div>
        </div>
      ) : (
        <div className="flex items-center gap-10">
          <FieldLabel icon={TagIcon} text="상담 태그" />
          <span className="text-body-small text-content-assistive">없음</span>
        </div>
      )}

      {description ? (
        <div className="flex flex-col gap-2">
          <FieldLabel icon={FileIcon} text="상담 설명" />
          <p className="text-body-small text-content-neutral break-words">{description}</p>
        </div>
      ) : (
        <div className="flex items-center gap-10">
          <FieldLabel icon={FileIcon} text="상담 설명" />
          <span className="text-body-small text-content-assistive">없음</span>
        </div>
      )}
    </section>
  );
}
