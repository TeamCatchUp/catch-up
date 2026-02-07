'use client';

import { useState, useMemo, useCallback } from 'react';
import { type TreeNode, getAllNodesFlat } from '@/shared/utils/tree';

interface UseTreeExplorerOptions<T extends TreeNode> {
  /** 현재 표시할 아이템 목록 */
  items: T[];
  /** 선택된 아이템 ID 배열 */
  selectedItems: string[];
}

interface UseTreeExplorerReturn<T extends TreeNode> {
  /** 검색어 상태 */
  searchQuery: string;
  /** 검색어 설정 함수 */
  setSearchQuery: (query: string) => void;
  /** 확장된 노드 ID Set */
  expandedNodes: Set<string>;
  /** 노드 확장/축소 토글 */
  toggleExpand: (nodeId: string, e: React.MouseEvent) => void;
  /** 검색 필터링된 아이템 */
  filteredItems: T[];
  /** 모든 아이템이 선택되었는지 여부 */
  isAllSelected: boolean;
  /** 검색어 초기화 */
  resetSearch: () => void;
}

/**
 * 트리 탐색기 공통 로직을 제공하는 훅
 * GithubExplorer, JiraExplorer에서 공통으로 사용되는 상태 및 함수 추출
 */
export function useTreeExplorer<T extends TreeNode>({
  items,
  selectedItems,
}: UseTreeExplorerOptions<T>): UseTreeExplorerReturn<T> {
  const [searchQuery, setSearchQuery] = useState('');
  const [expandedNodes, setExpandedNodes] = useState<Set<string>>(new Set());

  /** 노드 확장/축소 토글 */
  const toggleExpand = useCallback((nodeId: string, e: React.MouseEvent) => {
    e.stopPropagation();
    e.preventDefault();
    setExpandedNodes((prev) => {
      const newSet = new Set(prev);
      if (newSet.has(nodeId)) {
        newSet.delete(nodeId);
      } else {
        newSet.add(nodeId);
      }
      return newSet;
    });
  }, []);

  /** 검색 필터링된 아이템 */
  const filteredItems = useMemo<T[]>(() => {
    if (!searchQuery) return items;

    const searchLower = searchQuery.toLowerCase();
    const allFlatNodes = getAllNodesFlat(items);

    return allFlatNodes.filter((item) => {
      const name = (item as T & { name?: string }).name;
      return name?.toLowerCase().includes(searchLower);
    });
  }, [searchQuery, items]);

  /** 모든 아이템이 선택되었는지 여부 */
  const isAllSelected = useMemo(() => {
    if (filteredItems.length === 0) return false;
    return filteredItems.every((item) => selectedItems.includes(item.id));
  }, [filteredItems, selectedItems]);

  /** 검색어 초기화 */
  const resetSearch = useCallback(() => {
    setSearchQuery('');
  }, []);

  return {
    searchQuery,
    setSearchQuery,
    expandedNodes,
    toggleExpand,
    filteredItems,
    isAllSelected,
    resetSearch,
  };
}
