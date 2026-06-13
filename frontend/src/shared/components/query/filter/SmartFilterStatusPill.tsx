import { Button } from '../../ui/button';
import SmartFilterInfoTooltip from './SmartFilterInfoTooltip';

interface SmartFilterStatusPillProps {
  enabled: boolean;
  onApplyClick?: () => void;
}

export default function SmartFilterStatusPill({ enabled, onApplyClick }: SmartFilterStatusPillProps) {
  if (enabled) {
    return (
      <div className="bg-fill-normal-strong flex h-9 shrink-0 items-center gap-2.5 rounded-lg px-2.5">
        <SmartFilterInfoTooltip />
        <span className="text-body-xsmall text-text-normal-neutral font-medium whitespace-nowrap">
          스마트 필터 적용됨
        </span>
      </div>
    );
  }

  return (
    <div className="bg-fill-normal-strong flex h-9 shrink-0 items-center gap-2.5 rounded-lg px-2.5">
      <div className="flex items-center gap-2.5">
        <SmartFilterInfoTooltip />
        <span className="text-body-xsmall text-text-normal-alternative font-medium whitespace-nowrap">
          기본 검색 결과
        </span>
      </div>
      <span aria-hidden className="bg-line-normal-neutral h-4 w-px shrink-0" />
      <Button type="button" variant="text-primary-blue" size="sm" onClick={onApplyClick} className="px-1.5 py-1">
        스마트 필터 적용하기
      </Button>
    </div>
  );
}
