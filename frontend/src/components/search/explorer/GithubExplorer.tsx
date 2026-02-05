'use client';

import { useState, useEffect, useMemo } from 'react';
import IconGithub from '@/public/icons/logo/GitHub.svg';
import IconSpace from '@/public/icons/icon/folder_filled.svg';
import IconTag from '@/public/icons/icon/file_filled.svg';

import type { GithubNode } from '@/types/search/github';
import { useGithubExplorer } from '@/hooks/search/useGithubExplorer';
import { useTreeExplorer } from '@/hooks/search/useTreeExplorer';
import { ExplorerSearchInput } from './shared/ExplorerSearchInput';
import { ExplorerHeader } from './shared/ExplorerHeader';
import { ExplorerChildItem } from './shared/ExplorerChildItem';
import { ExplorerRootItem } from './shared/ExplorerRootItem';

interface GithubExplorerProps {
  selectedItems: string[];
  onToggleItem: (item: GithubNode) => void;
  currentRepo: GithubNode | null;
  onNavigate: (repo: GithubNode | null) => void;
  onClickBack: () => void;
}

type TabType = 'file' | 'PR' | 'Issue';

export const GithubExplorer = ({
  selectedItems,
  onToggleItem,
  currentRepo,
  onNavigate,
  onClickBack,
}: GithubExplorerProps) => {
  const { repositories, fileStructure, setFileStructure, isLoading, loadFileStructure } = useGithubExplorer(onNavigate);
  const [activeTab, setActiveTab] = useState<TabType>('file');

  /** 현재 표시할 아이템 계산 */
  const currentItems = useMemo(() => {
    if (currentRepo) {
      return fileStructure ? fileStructure.children || [] : [];
    }
    return repositories;
  }, [currentRepo, fileStructure, repositories]);

  /** 공통 트리 탐색 훅 사용 */
  const { searchQuery, setSearchQuery, expandedNodes, toggleExpand, filteredItems } = useTreeExplorer<GithubNode>({
    items: currentItems,
    selectedItems,
  });

  const handleRepoClick = (node: GithubNode) => {
    if (node.type === 'repo') {
      loadFileStructure(node);
    }
  };

  const handleGoBack = () => {
    if (fileStructure) {
      setFileStructure(null);
      onNavigate(null);
    } else {
      onClickBack();
    }
  };

  useEffect(() => {
    setActiveTab('file');
  }, [currentRepo]);

  const handleCheck = (item: GithubNode, e: React.MouseEvent) => {
    e.stopPropagation();
    e.preventDefault();
    onToggleItem(item);
  };

  const isAllSelected = useMemo(() => {
    if (filteredItems.length === 0) return false;

    if (currentRepo) {
      return selectedItems.includes(currentRepo.id) || filteredItems.every((item) => selectedItems.includes(item.id));
    }

    return filteredItems.every((item) => selectedItems.includes(item.id));
  }, [filteredItems, selectedItems, currentRepo]);

  const handleSelectAll = (e: React.MouseEvent) => {
    e.preventDefault();
    e.stopPropagation();
    if (activeTab !== 'file') return;

    if (currentRepo) {
      if (isAllSelected) {
        if (selectedItems.includes(currentRepo.id)) onToggleItem(currentRepo);
      } else {
        if (!selectedItems.includes(currentRepo.id)) onToggleItem(currentRepo);
      }
    } else {
      filteredItems.forEach((item) => {
        if (isAllSelected) {
          if (selectedItems.includes(item.id)) onToggleItem(item);
        } else {
          if (!selectedItems.includes(item.id)) onToggleItem(item);
        }
      });
    }
  };

  const renderItem = (node: GithubNode, depth: number = 0, isLastChild: boolean = false) => {
    const isExpanded = expandedNodes.has(node.id);
    const isSelected = selectedItems.includes(node.id) || Boolean(currentRepo && selectedItems.includes(currentRepo.id));
    const isFolder = node.type === 'tree';
    const isRepo = node.type === 'repo';

    // 아이콘 결정
    let TypeIcon = IconTag;
    if (isFolder) TypeIcon = IconSpace;

    if (isRepo) {
      return (
        <ExplorerRootItem
          key={node.id}
          node={node}
          isSelected={isSelected}
          icon={<IconGithub className="h-5 w-5 text-gray-50" />}
          onCheck={handleCheck}
          onNavigate={(n) => {
            handleRepoClick(n);
            onNavigate(n);
          }}
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
        isExpandable={isFolder}
        icon={<TypeIcon className="h-4.5 w-4.5 shrink-0 text-gray-50" />}
        onToggleExpand={toggleExpand}
        onCheck={handleCheck}
        renderChildren={(parent) =>
          parent.children?.map((child, index) =>
            renderItem(child as GithubNode, depth + 1, index === (parent.children?.length || 0) - 1),
          )
        }
      />
    );
  };

  /** 헤더 타이틀 렌더링 */
  const renderHeaderTitle = () => {
    if (currentRepo) {
      return (
        <div className="flex items-center justify-center gap-2.5">
          <div className="rounded-rounded border-neutral-3 bg-neutral-1 flex items-center justify-center gap-2.5 border p-1.5">
            <IconGithub className="h-5 w-5 text-gray-50" />
          </div>
          {currentRepo.name}
        </div>
      );
    }
    return <div>Github 내 Repository</div>;
  };

  return (
    <div className="flex h-full w-full flex-col gap-2.5">
      {/* 헤더 영역 */}
      <div className="center flex items-center gap-5 self-stretch px-1 pt-2">
        <ExplorerHeader
          title={renderHeaderTitle()}
          showBackButton={true}
          onBack={currentRepo ? () => { onNavigate(null); setSearchQuery(''); } : handleGoBack}
          showSelectAll={!currentRepo}
          isAllSelected={isAllSelected}
          onSelectAll={handleSelectAll}
        />
        <ExplorerSearchInput
          value={searchQuery}
          onChange={setSearchQuery}
          placeholder="Github 내 검색"
        />
      </div>

      {/* 탭 영역 (레포 내부일 때만) */}
      {currentRepo && (
        <div className="flex items-center justify-between self-stretch px-1">
          <div className="flex items-center gap-1">
            {(['file', 'PR', 'Issue'] as TabType[]).map((tab) => {
              const isActive = activeTab === tab;
              return (
                <button
                  key={tab}
                  type="button"
                  onMouseDown={(e) => e.preventDefault()}
                  onClick={() => setActiveTab(tab)}
                  className={`rounded-rounded flex items-center gap-1 px-3 py-1.5 ${
                    isActive
                      ? 'border-neutral-5 border bg-white'
                      : 'hover:bg-neutral-1 border border-transparent text-gray-50'
                  }`}
                >
                  <div className={`text-body-small truncate ${isActive ? 'text-gray-80' : 'text-gray-50'}`}>{tab}</div>
                </button>
              );
            })}
          </div>
          {activeTab === 'file' && (
            <ExplorerHeader
              title=""
              showBackButton={false}
              onBack={() => {}}
              showSelectAll={true}
              isAllSelected={isAllSelected}
              onSelectAll={handleSelectAll}
              selectAllLabel="전체 선택"
            />
          )}
        </div>
      )}

      {/* 아이템 목록 */}
      <div className="flex flex-col gap-1.5 self-stretch overflow-y-auto px-1 pb-4">
        {isLoading ? (
          <div className="flex flex-col items-center justify-center py-20">
            <div className="text-body-small text-gray-40">파일 목록을 불러오는 중...</div>
          </div>
        ) : !currentRepo || activeTab === 'file' ? (
          filteredItems.length > 0 ? (
            filteredItems.map((node, index) => renderItem(node, 0, index === filteredItems.length - 1))
          ) : (
            <div className="text-body-small text-gray-40 py-10 text-center">
              {searchQuery ? '검색 결과가 없습니다.' : '표시할 항목이 없습니다.'}
            </div>
          )
        ) : (
          <div className="flex flex-col items-center justify-center gap-2 py-10">
            <div className="text-body-small text-gray-40">준비 중인 기능입니다.</div>
          </div>
        )}
      </div>
    </div>
  );
};
