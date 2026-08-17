import { Avatar } from '@/shared/components/ui/avatar';
import { AvatarGroup, type AvatarGroupItem } from '@/shared/components/ui/avatar-group';
import { cn } from '@/shared/utils/cn';

export interface ReviewParticipant {
  id: string;
  name: string;
  /** 활동 설명(예: "1일 전 수정"). editing이면 파란색으로 강조된다 */
  description: string;
  editing: boolean;
  role: '작성자' | '리뷰어';
}

interface ReviewParticipantsCardProps {
  participants: readonly ReviewParticipant[];
  /** 헤더 우측 겹침 스택에 보일 아바타 목록 */
  stackAvatars: readonly AvatarGroupItem[];
}

/** 우측 패널의 "참여자" 카드 — 아바타 스택 헤더 + 참여자 행 목록. */
export default function ReviewParticipantsCard({ participants, stackAvatars }: ReviewParticipantsCardProps) {
  return (
    <section className="flex flex-col gap-4 p-4">
      <div className="flex items-center gap-4">
        <h3 className="text-body-small text-text-normal-alternative min-w-0 flex-1">참여자</h3>
        <AvatarGroup avatars={stackAvatars} size="small" />
      </div>
      {participants.map((participant) => (
        <div key={participant.id} className="flex items-center gap-4">
          <Avatar size="xlarge" src={null} className="rounded-xl" />
          <div className="flex min-w-0 flex-1 flex-col gap-0.5">
            <span className="text-body-small text-text-normal-neutral truncate">{participant.name}</span>
            <span
              className={cn(
                'text-body-small truncate',
                participant.editing ? 'text-text-primary-normal' : 'text-text-normal-assistive',
              )}
            >
              {participant.description}
            </span>
          </div>
          <span
            className={cn(
              'rounded-md2 text-body-xsmall flex shrink-0 items-center px-1.5 py-0.5',
              participant.role === '리뷰어'
                ? 'bg-fill-primary-normal-neutral text-text-primary-normal'
                : 'bg-fill-normal-strong text-text-normal-alternative',
            )}
          >
            {participant.role}
          </span>
        </div>
      ))}
    </section>
  );
}
