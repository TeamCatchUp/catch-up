import { Avatar } from '@/shared/components/ui/avatar';
import { AvatarGroup } from '@/shared/components/ui/avatar-group';

import type { DocumentOwner } from '../../types/llmWikiModel';

export interface WikiDocumentMetaProps {
  title: string;
  owners: readonly DocumentOwner[];
  timeLabel: string;
}

function OwnerMeta({ owners }: { owners: readonly DocumentOwner[] }) {
  if (owners.length === 0) {
    return (
      <>
        <Avatar size="small" className="border-line-normal-assistive rounded-xl" />
        <span className="text-body-xsmall text-text-normal-assistive truncate">담당자 없음</span>
      </>
    );
  }

  if (owners.length === 1) {
    return (
      <>
        <Avatar size="small" src={owners[0].profileImageUrl} className="border-line-normal-assistive rounded-xl" />
        <span className="text-body-xsmall text-text-normal-neutral truncate">{owners[0].displayName}</span>
      </>
    );
  }

  return (
    <>
      <AvatarGroup avatars={owners.map((owner) => ({ src: owner.profileImageUrl }))} size="small" max={3} />
      <span className="text-body-xsmall text-text-normal-neutral truncate">
        {owners[0].displayName}님 외 {owners.length - 1}명
      </span>
    </>
  );
}

export default function WikiDocumentMeta({ title, owners, timeLabel }: WikiDocumentMetaProps) {
  return (
    <div className="flex flex-col gap-3">
      <h1 className="text-heading-xlarge text-text-normal-strong min-w-0 truncate">{title}</h1>
      <div className="flex min-w-0 items-center gap-3">
        <OwnerMeta owners={owners} />
        <span className="text-body-xsmall text-text-normal-alternative shrink-0">{timeLabel}</span>
      </div>
    </div>
  );
}
