'use client';

import { useState } from 'react';
import IconJira from '@/public/icons/logo/Jira.svg';
import IconSpace from '@/public/icons/icon/epic.svg';
import IconTag from '@/public/icons/icon/task.svg';
import IconArrowRight from '@/public/icons/icon/arrow_right2.svg';
import IconArrowDown from '@/public/icons/icon/arrow_down.svg';
import IconBack from '@/public/icons/icon/arrow_left2.svg';
import IconSearch from '@/public/icons/icon/search.svg';
import IconCheckOn from '@/public/icons/icon/checkbox_checked.svg';
import IconCheckOff from '@/public/icons/icon/checkbox_unchecked.svg';
import IconConnector from '@/public/icons/icon/connector.svg';
import IconConnectorLast from '@/public/icons/icon/connector_last.svg';

import { JIRA_MOCK_DATA, JiraNode } from '@/constants/shared/jiraData';

interface JiraExplorerProps {
  selectedItems: string[];
  onToggleItem: (item: JiraNode) => void;
  currentProject: JiraNode | null;
  onNavigate: (project: JiraNode | null) => void;
  onClickBack: () => void;
}

export const JiraExplorer = ({
  selectedItems,
  onToggleItem,
  currentProject,
  onNavigate,
  onClickBack,
}: JiraExplorerProps) => {
  const [searchQuery, setSearchQuery] = useState('');
  const [expandedNodes, setExpandedNodes] = useState<Set<string>>(new Set());

  const toggleExpand = (nodeId: string, e: React.MouseEvent) => {
    e.stopPropagation();
    e.preventDefault();
    const newSet = new Set(expandedNodes);
    if (newSet.has(nodeId)) newSet.delete(nodeId);
    else newSet.add(nodeId);
    setExpandedNodes(newSet);
  };

  const handleCheck = (item: JiraNode, e: React.MouseEvent) => {
    e.stopPropagation();
    e.preventDefault();

    const isExpandable = item.type === 'project' || item.type === 'board';
    const isCurrentlySelected = selectedItems.includes(item.id);

    if (isExpandable && item.children) {
      if (isCurrentlySelected) {
        onToggleItem(item);
      } else {
        const allRelatedNodes = getAllChildNodes(item);
        allRelatedNodes.forEach((node) => {
          if (!selectedItems.includes(node.id)) {
            onToggleItem(node);
          }
        });
      }
    } else {
      onToggleItem(item);
    }
  };
  const getAllChildNodes = (node: JiraNode, nodes: JiraNode[] = []) => {
    nodes.push(node);
    if (node.children) {
      node.children.forEach((child) => getAllChildNodes(child, nodes));
    }
    return nodes;
  };

  const getAllNodesFlat = (nodes: JiraNode[], result: JiraNode[] = []) => {
    nodes.forEach((node) => {
      result.push(node);
      if (node.children) {
        getAllNodesFlat(node.children, result);
      }
    });
    return result;
  };
  const currentItems = currentProject ? currentProject.children || [] : JIRA_MOCK_DATA;
  const filteredItems = searchQuery
    ? getAllNodesFlat(currentItems).filter((item) => item.name.toLowerCase().includes(searchQuery.toLowerCase()))
    : currentItems;

  const isAllSelected = filteredItems.length > 0 && filteredItems.every((item) => selectedItems.includes(item.id));

  const handleSelectAll = (e: React.MouseEvent) => {
    e.preventDefault();
    e.stopPropagation();
    filteredItems.forEach((item) => {
      if (isAllSelected) {
        if (selectedItems.includes(item.id)) handleCheck(item, e);
      } else {
        if (!selectedItems.includes(item.id)) handleCheck(item, e);
      }
    });
  };

  const renderItem = (node: JiraNode, depth: number = 0, isLastChild: boolean = false) => {
    const isExpanded = expandedNodes.has(node.id);
    const isSelected = selectedItems.includes(node.id);
    const isExpandable = node.type === 'project' || node.type === 'board';
    const isRootProject = node.type === 'project' && !currentProject;

    let TypeIcon = node.type === 'ticket' ? IconTag : IconSpace;
    if (node.type === 'project') TypeIcon = IconJira;

    const Connector = isLastChild ? IconConnectorLast : IconConnector;

    if (isRootProject) {
      return (
        <div key={node.id} className="flex flex-col">
          <div
            className="hover:bg-neutral-1 flex h-10 shrink-0 cursor-pointer items-center justify-between gap-2.5 self-stretch rounded-xl bg-white py-1"
            onMouseDown={(e) => e.preventDefault()}
            onClick={(e) => onNavigate(node)}
          >
            <div className="flex items-center gap-2.5 p-1">
              <button
                type="button"
                onClick={(e) => handleCheck(node, e)}
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
                <IconJira className="h-5 w-5 text-gray-50" />
              </div>
              <div className="text-body-small text-gray-80 truncate">{node.name}</div>
            </div>
            <div className="flex items-center gap-2 pr-1">
              <div className="text-body-xsmall text-gray-30">
                {node.isPublic ? 'Public' : 'Private'} ∙ {node.lastEdited}
              </div>
              <div
                className="hover:bg-neutral-2 flex h-9 w-9 items-center justify-center rounded-lg p-1.5"
                onMouseDown={(e) => e.preventDefault()}
              >
                <IconArrowRight className="text-gray-70 h-6 w-6 shrink-0" />
              </div>
            </div>
          </div>
        </div>
      );
    }

    const INDENT_WIDTH = 38;

    return (
      <div key={node.id} className="flex flex-col">
        <div
          className="hover:bg-neutral-1 flex h-10 shrink-0 cursor-pointer items-center justify-between gap-2.5 self-stretch rounded-xl bg-white py-1 pr-2"
          onMouseDown={(e) => e.preventDefault()}
          onClick={(e) => {
            if (isExpandable) toggleExpand(node.id, e);
            else handleCheck(node, e);
          }}
        >
          <div className="flex flex-1 items-center overflow-hidden">
            <div className="ml-1 flex h-7 w-7 shrink-0 items-center justify-center">
              {isExpandable ? (
                <button
                  type="button"
                  onClick={(e) => toggleExpand(node.id, e)}
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
            {depth > 0 && <div style={{ width: `${(depth - 1) * INDENT_WIDTH}px` }} className="shrink-0" />}
            {depth > 0 && (
              <div className="flex shrink-0 items-center justify-center" style={{ width: `${INDENT_WIDTH}px` }}>
                <Connector className="text-gray-30 h-11.75 w-3.5" />
              </div>
            )}
            <div className="flex items-center gap-2.5 overflow-hidden p-1">
              <button
                type="button"
                onClick={(e) => handleCheck(node, e)}
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
              <TypeIcon className="h-4.5 w-4.5 shrink-0 text-gray-50" />
              <div className="text-body-small text-gray-80 truncate select-none">{node.name}</div>
            </div>
          </div>
          <div className="text-body-xsmall text-gray-30 shrink-0">
            {node.isPublic ? 'Public' : 'Private'} ∙ {node.lastEdited}
          </div>
        </div>
        {isExpanded && node.children && (
          <div className="flex flex-col">
            {node.children.map((child, index) =>
              renderItem(child, depth + 1, index === (node.children?.length || 0) - 1),
            )}
          </div>
        )}
      </div>
    );
  };

  return (
    <div className="flex h-full w-full flex-col gap-2.5">
      <div className="center flex items-center gap-5 self-stretch px-1 pt-2">
        <div className="flex flex-[1_0_0] items-center gap-1.5">
          {currentProject ? (
            <button
              type="button"
              className="hover:bg-neutral-3 flex h-7 w-7 items-center justify-center rounded-full p-0.5"
              onMouseDown={(e) => {
                e.preventDefault();
                e.stopPropagation();
              }}
              onClick={() => {
                onNavigate(null);
                setSearchQuery('');
              }}
            >
              <IconBack className="text-gray-9 h-5 w-5" />
            </button>
          ) : (
            <div className=""></div>
          )}
          <div className="text-body-medium text-gray-80 truncate select-none">
            {currentProject ? (
              currentProject.name
            ) : (
              <div className="flex items-center justify-center gap-2.5">
                <button
                  type="button"
                  className="hover:bg-neutral-3 flex h-7 w-7 items-center justify-center rounded-full p-0.5"
                  onMouseDown={(e) => e.preventDefault()}
                  onClick={() => onClickBack()}
                >
                  <IconBack className="text-gray-90 h-5 w-5" />
                </button>
                <div>Jira 프로젝트</div>{' '}
              </div>
            )}
          </div>
          <button
            type="button"
            className="hover:bg-neutral-1 ml-1 flex cursor-pointer items-center gap-0.5 rounded px-1 py-0.5"
            onMouseDown={(e) => {
              e.preventDefault();
              e.stopPropagation();
            }}
            onClick={handleSelectAll}
          >
            {isAllSelected ? (
              <IconCheckOn className="h-5 w-5 text-blue-50" />
            ) : (
              <IconCheckOff className="text-gray-30 h-5 w-5" />
            )}
            <div className="text-body-xsmall text-gray-70 select-none">전체 범위 적용</div>
          </button>
        </div>
        <div className="border-neutral-5 flex h-9 w-[273px] items-center gap-1 rounded-xl border bg-white px-2.5 py-1.5">
          <IconSearch className="h-5 w-5 shrink-0 text-gray-50" />
          <input
            className="text-body-small placeholder:text-gray-40 w-full truncate outline-none"
            placeholder="Jira 내 검색"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
          />
        </div>
      </div>

      <div className="flex flex-col gap-1.5 self-stretch overflow-y-auto px-1 pb-4">
        {filteredItems.length > 0 ? (
          filteredItems.map((node, index) => renderItem(node, 0, index === filteredItems.length - 1))
        ) : (
          <div className="text-body-small text-gray-40 py-10 text-center">검색 결과가 없습니다.</div>
        )}
      </div>
    </div>
  );
};
