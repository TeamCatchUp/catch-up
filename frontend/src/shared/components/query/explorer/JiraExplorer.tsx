'use client';

import { useMemo } from 'react';
import IconJira from '@/public/icons/logo/Jira.svg';
import IconSpace from '@/public/icons/icon/epic.svg';
import IconTag from '@/public/icons/icon/task.svg';

import type { JiraNode } from '@/shared/types/query/jira';
import { JIRA_MOCK_DATA } from '@/shared/mocks/search/jira';
import { useTreeExplorer } from '@/features/search/hooks/useTreeExplorer';
import { getAllChildNodes } from '@/shared/utils/tree';
import { ExplorerSearchInput } from './shared/ExplorerSearchInput';
import { ExplorerHeader } from './shared/ExplorerHeader';
import { ExplorerChildItem } from './shared/ExplorerChildItem';
import { ExplorerRootItem } from './shared/ExplorerRootItem';

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
  /** 현재 표시할 아이템 계산 */
  const currentItems = useMemo(() => {
    return currentProject ? currentProject.children || [] : JIRA_MOCK_DATA;
  }, [currentProject]);

  /** 공통 트리 탐색 훅 사용 */
  const { searchQuery, setSearchQuery, expandedNodes, toggleExpand, filteredItems, isAllSelected } =
    useTreeExplorer<JiraNode>({
      items: currentItems,
      selectedItems,
    });

  const handleCheck = (item: JiraNode, e: React.MouseEvent) => {
    e.stopPropagation();
    e.preventDefault();

    const isExpandable = item.type === 'project' || item.type === 'board';
    const isCurrentlySelected = selectedItems.includes(item.id);

    if (isExpandable && item.children && !isCurrentlySelected) {
      const allRelatedNodes = getAllChildNodes(item);
      allRelatedNodes.forEach((node) => {
        if (!selectedItems.includes(node.id)) {
          onToggleItem(node);
        }
      });
    } else {
      onToggleItem(item);
    }
  };

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

    // 아이콘 결정
    let TypeIcon = node.type === 'ticket' ? IconTag : IconSpace;

    if (isRootProject) {
      return (
        <ExplorerRootItem
          key={node.id}
          node={node}
          isSelected={isSelected}
          icon={<IconJira className="h-5 w-5 text-gray-50" />}
          onCheck={handleCheck}
          onNavigate={onNavigate}
        />
      );
    }

    return (
      <ExplorerChildItem
        key={node.id}
        node={node}
        depth={depth}
        isLastChild={isLastChild}
        isSelected={isSelected}
        isExpanded={isExpanded}
        isExpandable={isExpandable}
        icon={<TypeIcon className="h-4.5 w-4.5 shrink-0 text-gray-50" />}
        onToggleExpand={toggleExpand}
        onCheck={handleCheck}
        renderChildren={(parent) =>
          parent.children?.map((child, index) =>
            renderItem(child as JiraNode, depth + 1, index === (parent.children?.length || 0) - 1),
          )
        }
      />
    );
  };

  /** 헤더 타이틀 렌더링 */
  const renderHeaderTitle = () => {
    if (currentProject) {
      return currentProject.name;
    }
    return <div>Jira 프로젝트</div>;
  };

  return (
    <div className="flex h-full w-full flex-col gap-2.5">
      {/* 헤더 영역 */}
      <div className="center flex items-center gap-5 self-stretch px-1 pt-2">
        <ExplorerHeader
          title={renderHeaderTitle()}
          showBackButton={true}
          onBack={currentProject ? () => { onNavigate(null); setSearchQuery(''); } : onClickBack}
          showSelectAll={true}
          isAllSelected={isAllSelected}
          onSelectAll={handleSelectAll}
        />
        <ExplorerSearchInput
          value={searchQuery}
          onChange={setSearchQuery}
          placeholder="Jira 내 검색"
        />
      </div>

      {/* 아이템 목록 */}
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
