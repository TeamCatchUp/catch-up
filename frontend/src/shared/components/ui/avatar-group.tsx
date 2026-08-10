'use client';

import { cn } from '@/shared/utils/cn';

import { Avatar, type AvatarSize, avatarVariants } from './avatar';

/**
 * 겹쳐 쌓은 아바타 묶음. Figma의 두 컴포넌트에 대응한다.
 *
 * - `imagebox/profile`의 stack 변형(componentSet 582:2674) — 겹침 스택과 "+N" 칩
 * - `Group Button`(componentSet 961:5913) — 스택에 총원 라벨을 붙여 감싸는 알약(pill)
 *
 * 두 벌로 나누지 않은 이유는 Figma에서도 후자가 전자를 그대로 품는 구조이기 때문이다.
 * `totalLabel`(또는 `onClick`)이 오면 pill로 감싸고, 없으면 스택만 렌더한다 —
 * Figma `Group Button`의 `Show 총 인원수` 불린과 1:1로 대응한다.
 *
 * 소비처 시안: LLM Wiki 문서 메인의 참여자 그룹(17849:106441, 112×36).
 */

/** Figma가 stack 변형을 small·medium 두 크기로만 정의한다(xsmall·large·xlarge는 stack=1뿐). */
export type AvatarGroupSize = Extract<AvatarSize, 'small' | 'medium'>;

export interface AvatarGroupItem {
  src?: string | null;
  alt?: string;
}

/** Figma `stack=3 이상` — 아바타 3개까지 보이고 나머지는 "+N" 칩으로 접는다. */
const DEFAULT_MAX_VISIBLE = 3;

/** 겹침 6px. Figma auto-layout의 gap -6px. 첫 항목에는 걸지 않는다. */
const OVERLAP_CLASS = '-ml-1.5';

/**
 * pill이 버튼일 때 아바타 링을 배경색과 함께 바꾼다.
 * Figma가 hover/pressed 변형에서 아바타 stroke를 pill 배경과 같은 값으로 바꿔 두었다 —
 * 링을 기본값(#F7F7F8)으로 놔두면 배경이 어두워질 때 아바타 테두리만 밝게 떠 보인다.
 */
const INTERACTIVE_RING_CLASS =
  'group-hover:border-fill-normal-interaction-hover group-active:border-fill-normal-interaction-pressed group-disabled:border-fill-normal-strong';

/** Figma Group Button state=Default/Hover/Pressed/Inactive. 높이 36은 시안 고정값이다. */
const PILL_BASE_CLASS =
  'bg-fill-normal-strong border-line-normal-normal inline-flex h-9 w-fit items-center gap-2 rounded-full border px-2';

const PILL_INTERACTIVE_CLASS =
  'group hover:bg-fill-normal-interaction-hover active:bg-fill-normal-interaction-pressed active:border-line-normal-strong disabled:bg-fill-normal-interaction-inactive disabled:border-fill-normal-strong transition-colors';

interface AvatarGroupProps {
  /** 표시할 아바타 목록. 데이터는 전부 소비처가 넘긴다. */
  avatars: readonly AvatarGroupItem[];
  size?: AvatarGroupSize;
  /** 겹쳐 보일 최대 개수. 초과분은 "+N" 칩이 된다. */
  max?: number;
  /** 총원 라벨(시안 문구는 "12명"). 단위 표기는 소비처가 정한다. */
  totalLabel?: string;
  /** 넘기면 pill이 버튼이 된다. 시안에 클릭 동작이 없어 동작은 소비처 몫이다. */
  onClick?: () => void;
  disabled?: boolean;
  className?: string;
  'aria-label'?: string;
}

export function AvatarGroup({
  avatars,
  size = 'small',
  max = DEFAULT_MAX_VISIBLE,
  totalLabel,
  onClick,
  disabled = false,
  className,
  'aria-label': ariaLabel,
}: AvatarGroupProps) {
  const visibleAvatars = avatars.slice(0, Math.max(max, 0));
  const overflowCount = avatars.length - visibleAvatars.length;
  const isInteractive = Boolean(onClick);
  const ringClassName = isInteractive ? INTERACTIVE_RING_CLASS : undefined;

  const stack = (
    <span className="flex items-center">
      {visibleAvatars.map((avatar, index) => (
        <Avatar
          key={index}
          src={avatar.src}
          alt={avatar.alt}
          size={size}
          className={cn(index > 0 && OVERLAP_CLASS, ringClassName)}
        />
      ))}
      {overflowCount > 0 ? (
        // 칩은 아바타와 같은 원·링을 쓰고 배경과 글자만 다르다(Figma: 흰 배경 + Shadow/Button).
        <span
          className={cn(
            avatarVariants({ size }),
            'bg-fill-normal-normal text-text-normal-alternative text-body-xsmall shadow-button',
            visibleAvatars.length > 0 && OVERLAP_CLASS,
            ringClassName,
          )}
        >
          +{overflowCount}
        </span>
      ) : null}
    </span>
  );

  // pill 없이 스택만 쓰는 경우 = Figma `imagebox/profile` stack 변형 그대로.
  const withPill = totalLabel !== undefined || isInteractive;
  if (!withPill) {
    return <span className={cn('inline-flex w-fit items-center', className)}>{stack}</span>;
  }

  const label = totalLabel ? (
    <span className="text-body-xsmall text-text-normal-neutral group-disabled:text-text-normal-assistive">
      {totalLabel}
    </span>
  ) : null;

  if (!isInteractive) {
    return (
      <span className={cn(PILL_BASE_CLASS, className)} aria-label={ariaLabel}>
        {stack}
        {label}
      </span>
    );
  }

  return (
    <button
      type="button"
      onClick={onClick}
      disabled={disabled}
      aria-label={ariaLabel}
      className={cn(PILL_BASE_CLASS, PILL_INTERACTIVE_CLASS, className)}
    >
      {stack}
      {label}
    </button>
  );
}
