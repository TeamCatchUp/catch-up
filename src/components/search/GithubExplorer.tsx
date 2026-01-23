'use client';

import { useState, useEffect } from 'react';
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

import { GITHUB_MOCK_DATA, GithubNode } from '@/constants/githubRepoData';

const ConnectorLine = ({ className }: { className?: string }) => (
  <svg className={className} viewBox="0 0 14 47" fill="none" xmlns="http://www.w3.org/2000/svg">
    <path d="M1 0V47" stroke="#E5E5E5" strokeWidth="2" />
    <path d="M1 23.5H14" stroke="#E5E5E5" strokeWidth="2" />
  </svg>
);
const ConnectorLineLast = ({ className }: { className?: string }) => (
  <svg className={className} viewBox="0 0 14 47" fill="none" xmlns="http://www.w3.org/2000/svg">
    <path d="M1 0V23.5" stroke="#E5E5E5" strokeWidth="2" />
    <path d="M1 23.5H14" stroke="#E5E5E5" strokeWidth="2" />
  </svg>
);

interface GithubExplorerProps {
  selectedItems: string[];
  onToggleItem: (item: GithubNode) => void;
  currentRepo: GithubNode | null;
  onNavigate: (repo: GithubNode | null) => void;
}

type TabType = 'file' | 'PR' | 'Issue';

export const GithubExplorer = ({ selectedItems, onToggleItem, currentRepo, onNavigate }: GithubExplorerProps) => {
  const [searchQuery, setSearchQuery] = useState('');
  const [expandedNodes, setExpandedNodes] = useState<Set<string>>(new Set());
  const [activeTab, setActiveTab] = useState<TabType>('file');

  useEffect(() => {
    setActiveTab('file');
  }, [currentRepo]);

  const toggleExpand = (nodeId: string, e: React.MouseEvent) => {
    e.stopPropagation();
    e.preventDefault();
    const newSet = new Set(expandedNodes);
    if (newSet.has(nodeId)) newSet.delete(nodeId);
    else newSet.add(nodeId);
    setExpandedNodes(newSet);
  };

  const handleCheck = (item: GithubNode, e: React.MouseEvent) => {
    e.stopPropagation();
    e.preventDefault();
    onToggleItem(item);
  };

  const currentItems = currentRepo ? currentRepo.children || [] : GITHUB_MOCK_DATA;
  const filteredItems = currentItems.filter((item) => item.name.toLowerCase().includes(searchQuery.toLowerCase()));
  const isAllSelected = filteredItems.length > 0 && filteredItems.every((item) => selectedItems.includes(item.id));

  const handleSelectAll = (e: React.MouseEvent) => {
    e.preventDefault();
    e.stopPropagation();
    if (activeTab !== 'file') return;
    filteredItems.forEach((item) => {
      if (isAllSelected) {
        if (selectedItems.includes(item.id)) onToggleItem(item);
      } else {
        if (!selectedItems.includes(item.id)) onToggleItem(item);
      }
    });
  };

  const renderItem = (node: GithubNode, depth: number = 0, isLastChild: boolean = false) => {
    const isExpanded = expandedNodes.has(node.id);
    const isSelected = selectedItems.includes(node.id);
    const isFolder = node.type === 'folder';
    const isRepo = node.type === 'repo';

    let TypeIcon = IconTag;
    if (isFolder) TypeIcon = IconSpace;
    else if (isRepo) TypeIcon = IconGithub;

    const Connector = isLastChild ? IconConnectorLast || ConnectorLineLast : IconConnector || ConnectorLine;

    if (isRepo) {
      return (
        <div key={node.id} className="flex flex-col">
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
                    <IconArrowDown className="text-gray-70 h-5 w-5" />
                  ) : (
                    <IconArrowRight className="text-gray-70 h-5 w-5" />
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
              <IconBack className="text-gray-9 h-5 w-5" />
            </button>
          ) : (
            <div className="w-7"></div>
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
              'Github 내 Repository'
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
              <div className="text-body-xsmall text-gray-70 select-none">전체 범위 적용</div>
            </button>
          )}
        </div>
        <div className="border-neutral-5 flex h-9 w-[273px] items-center gap-1 rounded-xl border bg-white px-2.5 py-1.5">
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
        {!currentRepo || activeTab === 'file' ? (
          filteredItems.length > 0 ? (
            filteredItems.map((node, index) => renderItem(node, 0, index === filteredItems.length - 1))
          ) : (
            <div className="text-body-small text-gray-40 py-10 text-center">검색 결과가 없습니다.</div>
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
