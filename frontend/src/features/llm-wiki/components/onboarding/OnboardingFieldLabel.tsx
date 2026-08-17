import { cn } from '@/shared/utils/cn';

interface OnboardingFieldLabelProps {
  label: string;
  /** 시안의 필수 점 — 검증 실패 표시는 시안에 없어 시각만 있다 */
  required?: boolean;
  /** 카드 최상위 라벨은 heading(17), 분기·일정 안쪽 라벨은 body(15) */
  size?: 'heading' | 'body';
  className?: string;
}

// 온보딩 폼 라벨 + 필수 점
export default function OnboardingFieldLabel({
  label,
  required,
  size = 'heading',
  className,
}: OnboardingFieldLabelProps) {
  return (
    <div className={cn('flex items-start gap-1', className)}>
      <span className={cn(size === 'heading' ? 'text-heading-medium' : 'text-body-small', 'text-text-normal-normal')}>
        {label}
      </span>
      {required && (
        <span className="bg-status-destructive mt-1 size-[5px] shrink-0 rounded-full" aria-label="필수 입력" />
      )}
    </div>
  );
}
