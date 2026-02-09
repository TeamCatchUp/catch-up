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
  is_public?: boolean;
  last_edited?: string;
  children?: ApiFileNode[];
}

/** API 응답에서 받는 레포지토리 타입 */
interface ApiRepository {
  repository_id: number;
  name: string;
  is_public: boolean;
  updated_at: string;
}

/** 데이터에 고유 ID 주입 (재귀 함수) */
const transformNodes = (node: ApiFileNode, repoId: number): GithubNode => ({
  id: node.path || `repo-${repoId}`,
  name: node.name,
  type: node.type,
  is_public: node.is_public ?? true,
  last_edited: node.last_edited ?? '',
  children: node.children?.map((child) => transformNodes(child, repoId)),
});

export const useGithubExplorer = (onNavigate: (node: GithubNode | null) => void) => {
  const [fileStructure, setFileStructure] = useState<GithubNode | null>(null);
  const [isFileLoading, setIsFileLoading] = useState(false);

  const { data: rawRepos, isLoading: isRepoLoading, refetch } = useQuery(integrationQueries.github.installations());

  const repositories = useMemo<GithubNode[]>(() => {
    if (!rawRepos) return [];
    return (rawRepos as ApiRepository[]).map((repo) => ({
      id: String(repo.repository_id),
      name: repo.name,
      type: 'repo' as const,
      is_public: repo.is_public,
      last_edited: new Date(repo.updated_at).toLocaleDateString(),
      repository_id: repo.repository_id,
    }));
  }, [rawRepos]);

  /** 상세 파일 구조 로드 (백엔드 미구현 엔드포인트) */
  const loadFileStructure = useCallback(
    async (repo: GithubNode) => {
      if (!repo.repository_id) return;

      try {
        setIsFileLoading(true);
        const res = await api.get(`/api/github/read/repositories/${repo.repository_id}/files`);
        const structured = transformNodes(res.data as ApiFileNode, repo.repository_id);
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
