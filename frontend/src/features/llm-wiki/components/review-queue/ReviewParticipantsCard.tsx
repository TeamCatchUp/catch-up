import IconAssignmentFilled from '@/public/icons/icon/assignment_filled.svg';
import IconInfoFilled from '@/public/icons/icon/info_filled.svg';
import { Avatar } from '@/shared/components/ui/avatar';
import { cn } from '@/shared/utils/cn';

import OwnerAddPopover from './OwnerAddPopover';
import OwnerDetailPopover from './OwnerDetailPopover';
import type { ReviewQueueFilterOption } from './ReviewQueueFilterSearchPanel';

export type ParticipantRole = '담당자' | '채널 관리자';

export interface ReviewParticipant {
  id: string;
  /** [BE] user_id. 해제 요청 경로에 그대로 실린다 */
  userId: number;
  name: string;
  /** 활동 설명(예: "1일 전 수정"). 담당자별 활동 시각 API가 없어(B18) 지금은 비워 온다 */
  description?: string;
  /** 내 계정 여부 — 이름 뒤 "(나)" 표기 */
  isMe?: boolean;
  /** 역할 배지 — 겹치면 나란히 선다. 채널 관리자는 서버가 내 여부만 알려줘 내 행에만 붙는다 */
  roles: readonly ParticipantRole[];
  avatarSrc?: string | null;
}

export type OwnerNotice = 'no-owner' | 'other-owner';

/** 안내 배너 2종 — 내가 담당자면 배너 자체가 없다 */
const NOTICE_CONTENT = {
  'no-owner': { Icon: IconInfoFilled, message: '담당자가 지정되지 않아 구성원 누구나 검토할 수 있습니다.' },
  'other-owner': { Icon: IconAssignmentFilled, message: '담당자가 검토할 문서입니다' },
} as const;

/** 행 하나 — 아바타 40 + 이름·(나)·역할 태그, 아래줄은 활동 설명. 버튼 안에서도 쓰여 span으로만 짠다. */
function ParticipantRow({ participant }: { participant: ReviewParticipant }) {
  return (
    <span className="flex w-full items-center gap-4">
      <Avatar size="xlarge" src={participant.avatarSrc ?? null} className="border-line-normal-assistive rounded-xl" />
      <span className="flex min-w-0 flex-1 flex-col gap-0.5">
        <span className="flex min-w-0 items-center gap-1.5">
          <span className="text-body-small text-text-normal-neutral min-w-0 truncate">{participant.name}</span>
          {participant.isMe && <span className="text-body-small text-text-normal-assistive shrink-0">(나)</span>}
          {participant.roles.map((role) => (
            <span
              key={role}
              className={cn(
                'rounded-md2 text-body-xsmall flex shrink-0 items-center px-1.5 py-0.5',
                role === '채널 관리자'
                  ? 'bg-fill-primary-normal-neutral text-text-primary-normal'
                  : 'bg-fill-normal-strong text-text-normal-alternative',
              )}
            >
              {role}
            </span>
          ))}
        </span>
        {participant.description && (
          <span className="text-body-small text-text-normal-assistive truncate">{participant.description}</span>
        )}
      </span>
    </span>
  );
}

interface ReviewParticipantsCardProps {
  participants: readonly ReviewParticipant[];
  /** 담당자 유무·내 담당 여부로 갈리는 안내 배너. null이면 배너가 없다 */
  notice?: OwnerNotice | null;
  /** 지정 권한 — 채널 관리자 또는 담당자 본인(백엔드 can_manage_owners 규칙) */
  canAssign?: boolean;
  /** 해제 권한 — 관리자만. 담당자 본인도 못 한다 */
  canRemove?: boolean;
  /** 추가 드롭다운 후보 — 멤버 목록에서 현 담당자를 뺀 나머지 */
  candidates?: readonly ReviewQueueFilterOption[];
  onAssign?: (userIds: readonly number[]) => void;
  onRemove?: (userId: number) => void;
}

/** 우측 패널의 "담당자" 카드 — + 버튼 헤더, 안내 배너, 담당자 행과 해제 팝오버. */
export default function ReviewParticipantsCard({
  participants,
  notice = null,
  canAssign = false,
  canRemove = false,
  candidates = [],
  onAssign,
  onRemove,
}: ReviewParticipantsCardProps) {
  const noticeContent = notice === null ? null : NOTICE_CONTENT[notice];

  return (
    <section className="flex flex-col gap-4 p-4">
      <div className="flex items-center gap-4">
        <h3 className="text-body-small text-text-normal-alternative min-w-0 flex-1">담당자</h3>
        {canAssign && <OwnerAddPopover candidates={candidates} onAssign={(userIds) => onAssign?.(userIds)} />}
      </div>

      {noticeContent && (
        // 문구가 2줄이 될 수 있어 아이콘은 첫 줄에 맞춘다 — 줄바꿈은 어절 단위로만 끊는다
        <div className="bg-fill-normal-strong flex items-start gap-2 rounded-lg px-2 py-1.5">
          <noticeContent.Icon aria-hidden className="text-icon-normal-neutral size-4.5 shrink-0" />
          <span className="text-body-xsmall text-text-normal-neutral min-w-0 wrap-break-word break-keep">
            {noticeContent.message}
          </span>
        </div>
      )}

      {/* 행 목록 — 행마다 패딩 4를 갖고 행 사이는 2가 남는다 */}
      <div className="flex flex-col gap-0.5">
        {/* 해제는 실제 담당자 행에만 — 관리자 폴백 행은 지울 지정이 없다 */}
        {participants.map((participant) =>
          canRemove && participant.roles.includes('담당자') ? (
            <OwnerDetailPopover
              key={participant.id}
              name={participant.name}
              row={<ParticipantRow participant={participant} />}
              onRemove={() => onRemove?.(participant.userId)}
            >
              <button
                type="button"
                className="hover:bg-fill-normal-interaction-hover w-full cursor-pointer rounded-lg p-1 text-left transition-colors"
              >
                <ParticipantRow participant={participant} />
              </button>
            </OwnerDetailPopover>
          ) : (
            <div key={participant.id} className="p-1">
              <ParticipantRow participant={participant} />
            </div>
          ),
        )}
      </div>
    </section>
  );
}
