import IconArrowDown from '@/public/icons/icon/arrow_down.svg';
import IconArrowRight from '@/public/icons/icon/arrow_right2.svg';
import IconCheckOn from '@/public/icons/icon/checkbox_checked.svg';
import IconCheckOff from '@/public/icons/icon/checkbox_unchecked.svg';
import IconConnector from '@/public/icons/icon/connector.svg';
import IconConnectorLast from '@/public/icons/icon/connector_last.svg';

import { INDENT_WIDTH } from './explorerConstants';

/** 트리 노드의 기본 인터페이스 */
export interface BaseTreeNode {
  id: string;
  name: string;
  isPublic?: boolean;
  lastEdited?: string;
  children?: BaseTreeNode[];
}

interface TreeItemProps<T extends BaseTreeNode> {
  node: T;
  depth: number;
  isLastChild: boolean;
  isSelected: boolean;
  isExpanded: boolean;
  isExpandable: boolean;
  icon: React.ReactNode;
  onToggleExpand: (nodeId: string, e: React.MouseEvent) => void;
  onCheck: (node: T, e: React.MouseEvent) => void;
  renderChildren?: (node: T) => React.ReactNode;
}

export function ExplorerChildItem<T extends BaseTreeNode>({
  node,
  depth,
  isLastChild,
  isSelected,
  isExpanded,
  isExpandable,
  icon,
  onToggleExpand,
  onCheck,
  renderChildren,
}: TreeItemProps<T>) {
  const Connector = isLastChild ? IconConnectorLast : IconConnector;

  return (
    <div className="flex flex-col">
      <div
        className="hover:bg-neutral-1 flex h-10 shrink-0 cursor-pointer items-center justify-between gap-2.5 self-stretch rounded-xl bg-white py-1 pr-2"
        onMouseDown={(e) => e.preventDefault()}
        onClick={(e) => {
          if (isExpandable) onToggleExpand(node.id, e);
          else onCheck(node, e);
        }}
      >
        <div className="flex flex-1 items-center overflow-hidden">
          {/* 확장/축소 버튼 */}
          <div className="ml-1 flex h-7 w-7 shrink-0 items-center justify-center">
            {isExpandable ? (
              <button
                type="button"
                tabIndex={-1}
                onClick={(e) => {
                  e.stopPropagation();
                  onToggleExpand(node.id, e);
                }}
                onMouseDown={(e) => {
                  e.preventDefault();
                  e.stopPropagation();
                }}
                className="hover:bg-neutral-2 flex h-full w-full items-center justify-center rounded-lg"
              >
                {isExpanded ? (
                  <IconArrowDown className="text-gray-70 pointer-events-none h-5 w-5" />
                ) : (
                  <IconArrowRight className="text-gray-70 pointer-events-none h-5 w-5" />
                )}
              </button>
            ) : (
              <div className="w-5" />
            )}
          </div>

          {/* 들여쓰기 */}
          {depth > 0 && <div style={{ width: `${(depth - 1) * INDENT_WIDTH}px` }} className="shrink-0" />}

          {/* 연결선 */}
          {depth > 0 && (
            <div className="flex shrink-0 items-center justify-center" style={{ width: `${INDENT_WIDTH}px` }}>
              <Connector className="text-gray-30 h-11.75 w-3.5" />
            </div>
          )}

          {/* 체크박스 + 아이콘 + 이름 */}
          <div className="flex items-center gap-2.5 overflow-hidden p-1">
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
            {icon}
            <div className="text-body-small text-gray-80 truncate select-none">{node.name}</div>
          </div>
        </div>

        {/* 메타데이터 */}
        <div className="text-body-xsmall text-gray-30 shrink-0">
          {node.isPublic !== undefined && <>{node.isPublic ? 'Public' : 'Private'} ∙ </>}
          {node.lastEdited}
        </div>
      </div>

      {/* 자식 노드 */}
      {isExpanded && node.children && renderChildren && <div className="flex flex-col">{renderChildren(node as T)}</div>}
    </div>
  );
}
