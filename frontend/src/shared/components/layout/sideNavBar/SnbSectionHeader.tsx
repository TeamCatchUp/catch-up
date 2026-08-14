import { cn } from '@/shared/utils/cn';

/** 에이전트 섹션 머리글에 붙는 회색 알약. 머리글 안에서만 쓰인다 */
export function SnbBetaBadge() {
  return (
    <span className="bg-fill-normal-interaction-hover text-text-normal-alternative inline-flex h-5 shrink-0 items-center justify-center rounded px-1 text-[12px] leading-[1.5] font-medium">
      베타
    </span>
  );
}

export interface SnbSectionHeaderProps {
  label: string;
  /** 라벨 우측 슬롯. 지금 쓰이는 것은 베타 배지 하나뿐이다 */
  badge?: React.ReactNode;
  /**
   * 전달 시에만 머리글이 버튼이 된다. 잠정 어포던스 — 신 시안에는 없고
   * 구 사이드바의 질문 히스토리 진입점을 잇기 위한 것이다(시안 확인 대상).
   */
  onClick?: () => void;
  className?: string;
}

/** SNB 섹션 머리글. 에이전트·즐겨찾기·최근 질문·프로젝트가 공유한다 */
export default function SnbSectionHeader({ label, badge, onClick, className }: SnbSectionHeaderProps) {
  const content = (
    <>
      <span className="text-body-xsmall text-text-normal-alternative min-w-0 truncate">{label}</span>
      {badge}
    </>
  );
  const shellClass = cn('flex h-5 items-center rounded-lg px-2.5', badge ? 'gap-1.5' : 'gap-0.5', className);

  if (!onClick) {
    return <div className={shellClass}>{content}</div>;
  }

  return (
    <button
      type="button"
      onClick={onClick}
      className={cn(
        shellClass,
        'hover:bg-fill-normal-interaction-hover active:bg-fill-normal-interaction-pressed w-full cursor-pointer transition-colors',
      )}
    >
      {content}
    </button>
  );
}
