import IconArrowRight from '@/public/icons/icon/arrow_right2.svg';
import IconCheckOn from '@/public/icons/icon/checkbox_checked.svg';
import IconCheckOff from '@/public/icons/icon/checkbox_unchecked.svg';

import type { BaseTreeNode } from './ExplorerChildItem';

interface RootItemProps<T extends BaseTreeNode> {
  node: T;
  isSelected: boolean;
  icon: React.ReactNode;
  onCheck: (node: T, e: React.MouseEvent) => void;
  onNavigate: (node: T) => void;
}

export function ExplorerRootItem<T extends BaseTreeNode>({
  node,
  isSelected,
  icon,
  onCheck,
  onNavigate,
}: RootItemProps<T>) {
  return (
    <div className="flex flex-col">
      <div
        className="hover:bg-neutral-1 flex h-10 shrink-0 cursor-pointer items-center justify-between gap-2.5 self-stretch rounded-xl bg-white py-1"
        onMouseDown={(e) => e.preventDefault()}
        onClick={() => onNavigate(node)}
      >
        <div className="flex items-center gap-2.5 p-1">
          <button
            onClick={(e) => onCheck(node, e)}
            onMouseDown={(e) => {
              e.preventDefault();
              e.stopPropagation();
            }}
            className="shrink-0"
          >
            {isSelected ? (
              <IconCheckOn className="h-5 w-5 text-blue-50" />
            ) : (
              <IconCheckOff className="text-gray-30 h-5 w-5" />
            )}
          </button>
          <div className="rounded-rounded border-neutral-3 bg-neutral-1 flex items-center justify-center gap-2.5 p-1.5">
            {icon}
          </div>
          <div className="text-body-small text-gray-80 truncate">{node.name}</div>
        </div>
        <div className="flex items-center gap-2 pr-1">
          <div className="text-body-xsmall text-gray-30">
            {node.is_public !== undefined && <>{node.is_public ? 'Public' : 'Private'} ∙ </>}
            {node.last_edited}
          </div>
          <div className="hover:bg-neutral-2 flex h-9 w-9 items-center justify-center rounded-lg p-1.5">
            <IconArrowRight className="text-gray-70 h-6 w-6 shrink-0" />
          </div>
        </div>
      </div>
    </div>
  );
}
