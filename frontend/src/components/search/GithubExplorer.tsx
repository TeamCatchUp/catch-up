'use client';

import { useState, useEffect, useMemo } from 'react';
import IconGithub from '@/public/icons/logo/GitHub.svg';
import IconSpace from '@/public/icons/icon/folder_filled.svg';
import IconTag from '@/public/icons/icon/file_filled.svg';
import IconArrowRight from '@/public/icons/icon/arrow_right2.svg';
import IconArrowDown from '@/public/icons/icon/arrow_down.svg';
import IconBack from '@/public/icons/icon/arrow_left2.svg';
import IconSearch from '@/public/icons/icon/search.svg';
import IconCheckOn from '@/public/icons/icon/checkbox_checked.svg';
import IconCheckOff from '@/public/icons/icon/checkbox_unchecked.svg';
import IconConnector from '@/public/icons/icon/connector.svg';
import IconConnectorLast from '@/public/icons/icon/connector_last.svg';

import type { GithubNode } from '@/types/search/github';
import { useGithubExplorer } from '@/hooks/search/useGithubExplorer';
import { useTreeExplorer } from '@/hooks/search/useTreeExplorer';

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

    // 레포 내부라면: 부모(currentRepo)가 선택되어 있거나, 모든 자식이 개별 선택되어 있는지 확인
    if (currentRepo) {
      return selectedItems.includes(currentRepo.id) || filteredItems.every((item) => selectedItems.includes(item.id));
    }

    // 최상위 목록이라면: 필터링된 레포들이 모두 선택되어 있는지 확인
    return filteredItems.every((item) => selectedItems.includes(item.id));
  }, [filteredItems, selectedItems, currentRepo]);
  const handleSelectAll = (e: React.MouseEvent) => {
    e.preventDefault();
    e.stopPropagation();
    if (activeTab !== 'file') return;

    if (currentRepo) {
      // [수정] 레포 내부일 경우, 개별 자식들이 아닌 currentRepo(type: 'repo') 자체를 토글
      // 이미 선택되어 있다면(isAllSelected) 해제, 아니면 선택
      if (isAllSelected) {
        if (selectedItems.includes(currentRepo.id)) onToggleItem(currentRepo);
      } else {
        if (!selectedItems.includes(currentRepo.id)) onToggleItem(currentRepo);
      }
    } else {
      // 최상위 목록일 때는 기존 필터링된 레포지토리들을 토글
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
    const isSelected = selectedItems.includes(node.id) || (currentRepo && selectedItems.includes(currentRepo.id));
    const isFolder = node.type === 'tree';
    const isRepo = node.type === 'repo';
    let TypeIcon = IconTag;
    if (isFolder) TypeIcon = IconSpace;
    else if (isRepo) TypeIcon = IconGithub;

    const Connector = isLastChild ? IconConnectorLast : IconConnector;

    if (isRepo) {
      return (
        <div key={node.id} className="flex flex-col" onClick={() => handleRepoClick(node)}>
          <div
            className="hover:bg-neutral-1 flex h-10 shrink-0 cursor-pointer items-center justify-between gap-2.5 self-stretch rounded-xl bg-white py-1"
            onMouseDown={(e) => e.preventDefault()}
            onClick={(e) => onNavigate(node)}
          >
            <div className="flex items-center gap-2.5 p-1">
              <button
                onClick={(e) => handleCheck(node, e)}
                onMouseDown={(e) => {
                  e.preventDefault();
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
                <IconGithub className="h-5 w-5 text-gray-50" />
              </div>
              <div className="text-body-small text-gray-80 truncate">{node.name}</div>
            </div>
            <div className="flex items-center gap-2 pr-1">
              <div className="text-body-xsmall text-gray-30">
                {node.isPublic ? 'Public' : 'Private'} ∙ {node.lastEdited}
              </div>
              <div className="hover:bg-neutral-2 flex h-9 w-9 items-center justify-center rounded-lg p-1.5">
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
            if (isFolder) toggleExpand(node.id, e);
            else handleCheck(node, e);
          }}
        >
          <div className="flex flex-1 items-center overflow-hidden">
            <div className="ml-1 flex h-7 w-7 shrink-0 items-center justify-center">
              {isFolder ? (
                <button
                  type="button"
                  tabIndex={-1}
                  onClick={(e) => {
                    e.stopPropagation();
                    toggleExpand(node.id, e);
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

            {depth > 0 && <div style={{ width: `${(depth - 1) * INDENT_WIDTH}px` }} className="shrink-0" />}

            {depth > 0 && (
              <div className="flex shrink-0 items-center justify-center" style={{ width: `${INDENT_WIDTH}px` }}>
                <Connector className="text-gray-30 h-11.75 w-3.5" />
              </div>
            )}
            <div className="flex items-center gap-2.5 overflow-hidden p-1">
              <button
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
          {currentRepo ? (
            <button
              type="button"
              className="hover:bg-neutral-3 flex h-7 w-7 items-center justify-center rounded-full p-0.5"
              onMouseDown={(e) => e.preventDefault()}
              onClick={() => {
                onNavigate(null);
                setSearchQuery('');
              }}
            >
              <IconBack className="text-gray-90 h-5 w-5" />
            </button>
          ) : (
            <div className=""></div>
          )}
          <div className="text-body-medium text-gray-80 truncate select-none">
            {currentRepo ? (
              <div className="flex items-center justify-center gap-2.5">
                <div className="rounded-rounded border-neutral-3 bg-neutral-1 flex items-center justify-center gap-2.5 border p-1.5">
                  <IconGithub className="h-5 w-5 text-gray-50" />
                </div>
                {currentRepo.name}
              </div>
            ) : (
              <div className="flex items-center justify-center gap-1">
                <button
                  type="button"
                  className="hover:bg-neutral-3 flex h-7 w-7 items-center justify-center rounded-full p-0.5 mr-3"
                  onMouseDown={(e) => e.preventDefault()}
                  onClick={handleGoBack}
                >
                  <IconBack className="text-gray-90 h-5 w-5" />
                </button>
                <div>Github 내 Repository</div>
              </div>
            )}
          </div>
          {!currentRepo && (
            <button
              className="hover:bg-neutral-1 ml-1 flex cursor-pointer items-center gap-0.5 rounded px-1 py-0.5"
              onMouseDown={(e) => e.preventDefault()}
              onClick={handleSelectAll}
            >
              {isAllSelected ? (
                <IconCheckOn className="h-5 w-5 text-blue-50" />
              ) : (
                <IconCheckOff className="text-gray-30 h-5 w-5" />
              )}
              <div className="text-body-xsmall text-gray-70 select-none whitespace-nowrap">전체 범위 적용</div>
            </button>
          )}
        </div>
        <div className="border-neutral-5 flex h-9 w-68.25 items-center gap-1 rounded-xl border bg-white px-2.5 py-1.5">
          <IconSearch className="h-5 w-5 shrink-0 text-gray-50" />
          <input
            className="text-body-small placeholder:text-gray-40 w-full truncate outline-none"
            placeholder="Github 내 검색"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
          />
        </div>
      </div>

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
            <button
              className="hover:bg-neutral-1 flex cursor-pointer items-center gap-0.5 rounded p-1"
              onMouseDown={(e) => e.preventDefault()}
              onClick={handleSelectAll}
            >
              <div className="flex items-center gap-2.5 px-1">
                {isAllSelected ? (
                  <IconCheckOn className="h-5 w-5 text-blue-50" />
                ) : (
                  <IconCheckOff className="text-gray-30 h-5 w-5" />
                )}
              </div>
              <div className="text-body-xsmall text-gray-70 select-none">전체 선택</div>
            </button>
          )}
        </div>
      )}
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
