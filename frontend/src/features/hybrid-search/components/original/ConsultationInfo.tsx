// 상담 정보 섹션 — 담당자 / 상담 태그 / 상담 설명.
// 태그가 없으면 '없음' placeholder 변형으로 렌더.

import type { OriginalMetadata } from '@/features/hybrid-search/types/originalApi';
import FileIcon from '@/public/icons/icon/file.svg';
import PersonFilledIcon from '@/public/icons/icon/person_filled.svg';
import TagIcon from '@/public/icons/icon/tag.svg';

interface ConsultationInfoProps {
  metadata: OriginalMetadata;
}

interface FieldLabelProps {
  icon: typeof TagIcon;
  text: string;
}

function FieldLabel({ icon: Icon, text }: FieldLabelProps) {
  return (
    <span className="flex shrink-0 items-center gap-4">
      <Icon className="text-icon-alternative h-5.5 w-5.5" />
      <span className="text-body-small text-content-alternative">{text}</span>
    </span>
  );
}

export default function ConsultationInfo({ metadata }: ConsultationInfoProps) {
  // 담당자 — 응답엔 assignee_id만 오므로 managers[]에서 이름을 조회.
  const assignment = metadata.assignment;
  const assigneeId = assignment?.assignee_id;
  const assigneeName = assigneeId
    ? assignment?.managers?.find((manager) => manager.manager_id === assigneeId)?.name?.trim()
    : undefined;
  const description = metadata.description?.trim();
  const tagNames = (metadata.tags ?? [])
    .map((tag) => tag.name?.trim())
    .filter((name): name is string => Boolean(name));

  return (
    <section className="bg-fill-strong border-edge-neutral flex w-full flex-col gap-3 rounded-xl border px-5 py-4">
      <div className="flex items-center gap-10">
        <FieldLabel icon={PersonFilledIcon} text="담당자" />
        <span className="text-body-small text-content-neutral min-w-0 flex-1 truncate">
          {assigneeName ?? <span className="text-content-assistive">없음</span>}
        </span>
      </div>

      <div className="flex flex-col gap-2">
        <FieldLabel icon={TagIcon} text="상담 태그" />
        {tagNames.length > 0 ? (
          <ul className="flex flex-wrap gap-x-1.5 gap-y-3">
            {tagNames.map((name, index) => (
              <li
                key={`${name}-${index}`}
                className="bg-fill-primary-normal-neutral text-body-xsmall text-content-primary rounded-md2 px-1.5 py-0.5 font-medium"
              >
                {name}
              </li>
            ))}
          </ul>
        ) : (
          <span className="text-body-small text-content-assistive">없음</span>
        )}
      </div>

      <div className="flex flex-col gap-2">
        <FieldLabel icon={FileIcon} text="상담 설명" />
        {description ? (
          <p className="text-body-small text-content-neutral break-words">{description}</p>
        ) : (
          <span className="text-body-small text-content-assistive">없음</span>
        )}
      </div>
    </section>
  );
}
