import Link from 'next/link';

import IconMore from '@/public/icons/icon/kebab_horizontal.svg';
import { cn } from '@/shared/utils/cn';

export interface SnbChatTitleRowProps {
  label: string;
  selected?: boolean;
  /** 전달 시 링크로 렌더한다 — 새 탭·미들클릭·prefetch가 필요한 행에 쓴다 */
  href?: string;
  onClick?: () => void;
  /** 전달 시에만 더보기(⋯)를 만든다. 메뉴 내용은 이 컴포넌트가 모른다 */
  onMoreClick?: () => void;
  className?: string;
}

/**
 * SNB 최근 질문 행. 더보기 버튼이 행 안에 들어가야 해서 행 자체는 버튼이 아니라 컨테이너다.
 */
export default function SnbChatTitleRow({
  label,
  selected = false,
  href,
  onClick,
  onMoreClick,
  className,
}: SnbChatTitleRowProps) {
  // 라벨 span이 flex 아이템이어야 truncate가 동작한다
  const titleClass = 'flex min-w-0 flex-1 cursor-pointer';
  const title = (
    <span
      className={cn(
        'text-body-small min-w-0 truncate text-left',
        selected ? 'text-text-primary-normal' : 'text-text-normal-normal',
      )}
    >
      {label}
    </span>
  );

  return (
    <div
      className={cn(
        'group flex h-9 w-full items-center gap-1 rounded-lg px-2.5 py-1.5 transition-colors',
        // 행이 버튼이 아니라서 pressed는 제목 요소의 :active를 has()로 받는다.
        // 제목은 href 유무에 따라 링크나 버튼이므로 둘 다 받는다
        'hover:bg-fill-normal-interaction-hover',
        'has-[a:active]:bg-fill-normal-interaction-pressed has-[button:active]:bg-fill-normal-interaction-pressed',
        selected && 'bg-fill-primary-normal-neutral hover:bg-fill-primary-normal-interaction-hover-assistive',
        className,
      )}
    >
      {href ? (
        <Link href={href} onClick={onClick} aria-current={selected ? 'page' : undefined} className={titleClass}>
          {title}
        </Link>
      ) : (
        <button type="button" onClick={onClick} aria-current={selected ? 'page' : undefined} className={titleClass}>
          {title}
        </button>
      )}
      {onMoreClick && (
        <button
          type="button"
          aria-label={`${label} 더보기`}
          onClick={onMoreClick}
          // hover만 걸면 키보드로 도달할 수 없어 focus-within을 함께 본다
          className="text-icon-normal-neutral hover:bg-fill-normal-interaction-hover hidden size-5.5 shrink-0 cursor-pointer items-center justify-center rounded-full group-focus-within:flex group-hover:flex"
        >
          <IconMore aria-hidden className="size-4.5" />
        </button>
      )}
    </div>
  );
}
