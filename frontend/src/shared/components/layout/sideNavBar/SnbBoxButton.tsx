import IconArrowRight from '@/public/icons/icon/arrow_right.svg';
import { cn } from '@/shared/utils/cn';

export interface SnbBoxButtonProps {
  label: string;
  /** 라벨 앞 아이콘. 생략하면 자리를 만들지 않는다 */
  Icon?: React.ComponentType<React.SVGProps<SVGSVGElement>>;
  /** 라벨 앞부분을 강조색으로 낸다 — "Wiki 온보딩 중"의 "Wiki"가 그 자리다 */
  accentPrefix?: string;
  onClick?: () => void;
  className?: string;
}

/**
 * SNB 안의 테두리 박스형 진입 버튼. 메뉴 행과 달리 우측 화살표로 다음 단계를 가리킨다.
 */
export default function SnbBoxButton({ label, Icon, accentPrefix, onClick, className }: SnbBoxButtonProps) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={cn(
        'border-line-normal-neutral hover:bg-fill-normal-interaction-hover active:bg-fill-normal-interaction-pressed flex h-12 w-full cursor-pointer items-center gap-2.5 rounded-xl border px-3 transition-colors',
        className,
      )}
    >
      {Icon && <Icon aria-hidden className="text-icon-primary-normal size-5 shrink-0" />}
      <span className="text-body-small text-text-normal-normal min-w-0 flex-1 truncate text-left">
        {accentPrefix && <span className="text-text-primary-normal">{accentPrefix}</span>}
        {accentPrefix ? ` ${label}` : label}
      </span>
      <IconArrowRight aria-hidden className="text-icon-normal-neutral size-6 shrink-0" />
    </button>
  );
}
