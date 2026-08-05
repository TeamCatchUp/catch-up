import { cn } from '@/shared/utils/cn';

interface SnbMenuItemProps {
  /** 좌측 아이콘. 생략하면 아이콘 자리를 만들지 않는다 */
  Icon?: React.ComponentType<React.SVGProps<SVGSVGElement>>;
  label: string;
  /** 현재 선택된 항목인지 */
  selected?: boolean;
  /** 확장형 메뉴 헤더로 쓸 때의 펼침 상태. 지정하면 aria-expanded가 붙는다 */
  expanded?: boolean;
  onClick?: () => void;
  /** 우측 슬롯 — 확장형 메뉴의 화살표 등 */
  trailing?: React.ReactNode;
  className?: string;
}

/**
 * 설정 사이드바와 커넥터 목록이 공유하는 메뉴 항목.
 * Figma 디자인 시스템 `SNB/menu` 컴포넌트에 대응한다.
 */
export default function SnbMenuItem({
  Icon,
  label,
  selected = false,
  expanded,
  onClick,
  trailing,
  className,
}: SnbMenuItemProps) {
  return (
    <button
      type="button"
      onClick={onClick}
      aria-current={selected ? 'page' : undefined}
      aria-expanded={expanded}
      className={cn(
        'flex h-9 w-full cursor-pointer items-center justify-between gap-3 rounded-lg px-2.5 py-1.5 transition-colors',
        /*
         * Figma는 Default/Hover/Pressed/Selected/Selected_hover 5상태를 알파
         * 오버레이로 구분하지만, 코드의 interaction 토큰은 아직 solid neutral
         * 세대라 알파 단계를 그대로 못 낸다. Selected 는 `fill-normal-strong`으로
         * 정확히 일치하고, hover/pressed 는 상대 순서(hover < pressed)를 지키는
         * 기존 토큰으로 낸다. 알파 오버레이 전환은 디자인 시스템 차원의 별도 작업이다.
         */
        'hover:bg-fill-normal-interaction-hover active:bg-fill-normal-interaction-pressed',
        selected && 'bg-fill-normal-strong',
        className,
      )}
    >
      <span className="flex min-w-0 flex-1 items-center gap-3">
        {Icon && <Icon className="text-icon-normal-normal size-5.5 shrink-0" />}
        <span className="text-body-small text-text-normal-normal truncate text-left">{label}</span>
      </span>
      {trailing}
    </button>
  );
}
