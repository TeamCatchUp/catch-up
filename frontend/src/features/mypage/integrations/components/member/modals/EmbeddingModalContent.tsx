import CheckboxIcon from '@/shared/components/ui/checkbox-icon';
import { cn } from '@/shared/utils/cn';

import type { SyncTargetItem } from '../../../types/syncModel';

export interface EmbeddingContentProps {
  targets: SyncTargetItem[];
  selectedItems: Set<string>;
  onToggleItem: (targetId: string) => void;
}

/** 임베딩 모달 항목 목록 (모든 서비스 공통) */
export default function EmbeddingModalContent({ targets, selectedItems, onToggleItem }: EmbeddingContentProps) {
  return (
    <div className="border-edge-assistive overflow-clip rounded-xl border">
      <div className="thin-scrollbar flex max-h-101 flex-col overflow-y-auto">
        {targets.map((target) => {
          const checked = selectedItems.has(target.target_id);
          const disabled = !target.is_accessible;

          return (
            <button
              key={target.target_id}
              type="button"
              disabled={disabled}
              onClick={() => onToggleItem(target.target_id)}
              className={cn(
                'border-edge-assistive flex w-full items-center gap-5 border-b px-5 py-3 last:border-b-0',
                disabled ? 'cursor-not-allowed opacity-50' : 'cursor-pointer',
              )}
            >
              <span className="text-body-small text-content-neutral min-w-0 flex-1 truncate text-left">
                {target.display_name}
              </span>
              {!disabled && <CheckboxIcon checked={checked} className="size-6" />}
            </button>
          );
        })}
        {targets.length === 0 && (
          <div className="flex h-12 items-center justify-center">
            <span className="text-body-small text-content-assistive">항목이 없습니다.</span>
          </div>
        )}
      </div>
    </div>
  );
}
