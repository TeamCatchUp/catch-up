'use client';

import { cn } from '@/shared/utils/cn';

import { Avatar, type AvatarSize, avatarVariants } from './avatar';

/**
 * 겹쳐 쌓은 아바타 묶음과 "+N" 칩.
 * `totalLabel`이나 `onClick`이 오면 총원 라벨을 붙인 알약(pill)으로 감싸고, 없으면 스택만 렌더한다.
 */

/** 겹침 스택이 정의된 크기는 small·medium 둘뿐이다. */
export type AvatarGroupSize = Extract<AvatarSize, 'small' | 'medium'>;

export interface AvatarGroupItem {
  src?: string | null;
  alt?: string;
}

/** 아바타 3개까지 보이고 나머지는 "+N" 칩으로 접는다. */
const DEFAULT_MAX_VISIBLE = 3;

/** 아바타 간 겹침. 첫 항목에는 걸지 않는다. */
const OVERLAP_CLASS = '-ml-1.5';

/**
 * pill이 버튼일 때 아바타 링을 배경색과 함께 바꾼다.
 * 링을 기본값으로 두면 배경이 어두워질 때 테두리만 밝게 떠 보인다.
 */
const INTERACTIVE_RING_CLASS =
  'group-hover:border-fill-normal-interaction-hover group-active:border-fill-normal-interaction-pressed group-disabled:border-fill-normal-strong';

/** pill 셸. 높이는 시안 고정값이다. */
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
  /** 총원 라벨. 단위 표기는 소비처가 정한다. */
  totalLabel?: string;
  /** 넘기면 pill이 버튼이 된다. 동작은 소비처 몫이다. */
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
        // 칩은 아바타와 같은 원·링을 쓰고 배경과 글자만 다르다.
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

  // 라벨도 클릭도 없으면 pill 없이 스택만 렌더한다.
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
