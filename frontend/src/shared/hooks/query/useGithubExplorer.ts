import { useCallback,useMemo, useState } from 'react';
import { useQuery } from '@tanstack/react-query';

import api from '@/shared/api/client';
import { integrationQueries } from '@/shared/queries/integration.queries';
import type { GithubNode } from '@/shared/types/query/github';

/** API 응답에서 받는 파일 구조 타입 */
interface ApiFileNode {
  name: string;
  type: 'tree' | 'blob';
  path?: string;
  isPublic?: boolean;
  lastEdited?: string;
  children?: ApiFileNode[];
}

/** API 응답에서 받는 레포지토리 타입 */
interface ApiRepository {
  repositoryId: number;
  name: string;
  isPublic: boolean;
  updatedAt: string;
}

/** 데이터에 고유 ID 주입 (재귀 함수) */
const transformNodes = (node: ApiFileNode, repoId: number): GithubNode => ({
  id: node.path || `repo-${repoId}`,
  name: node.name,
  type: node.type,
  isPublic: node.isPublic ?? true,
  lastEdited: node.lastEdited ?? '',
  children: node.children?.map((child) => transformNodes(child, repoId)),
});

export const useGithubExplorer = (onNavigate: (node: GithubNode | null) => void) => {
  const [fileStructure, setFileStructure] = useState<GithubNode | null>(null);
  const [isFileLoading, setIsFileLoading] = useState(false);

  const { data: rawRepos, isLoading: isRepoLoading, refetch } = useQuery(integrationQueries.github.installations());

  const repositories = useMemo<GithubNode[]>(() => {
    if (!rawRepos) return [];
    return (rawRepos as ApiRepository[]).map((repo) => ({
      id: String(repo.repositoryId),
      name: repo.name,
      type: 'repo' as const,
      isPublic: repo.isPublic,
      lastEdited: new Date(repo.updatedAt).toLocaleDateString(),
      repositoryId: repo.repositoryId,
    }));
  }, [rawRepos]);

  /** 상세 파일 구조 로드 (백엔드 미구현 엔드포인트) */
  const loadFileStructure = useCallback(
    async (repo: GithubNode) => {
      if (!repo.repositoryId) return;

      try {
        setIsFileLoading(true);
        const res = await api.get(`/api/github/read/repositories/${repo.repositoryId}/files`);
        const structured = transformNodes(res.data as ApiFileNode, repo.repositoryId);
        setFileStructure(structured);
        onNavigate(structured);
      } catch (err) {
        console.error('Failed to load file structure:', err);
      } finally {
        setIsFileLoading(false);
      }
    },
    [onNavigate],
  );

  return {
    repositories,
    fileStructure,
    setFileStructure,
    isLoading: isRepoLoading || isFileLoading,
    loadFileStructure,
    refresh: refetch,
  };
};
