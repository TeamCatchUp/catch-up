import { useState, useEffect } from 'react';
import { githubService } from '@/shared/api/github';
import type { GithubNode } from '@/types/search/github';

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

export const useGithubExplorer = (onNavigate: (node: GithubNode | null) => void) => {
  const [repositories, setRepositories] = useState<GithubNode[]>([]);
  const [fileStructure, setFileStructure] = useState<GithubNode | null>(null);
  const [isLoading, setIsLoading] = useState(false);

  /** 데이터에 고유 ID 주입 (재귀 함수) */
  const transformNodes = (node: ApiFileNode, repoId: number): GithubNode => ({
    id: node.path || `repo-${repoId}`,
    name: node.name,
    type: node.type,
    isPublic: node.isPublic ?? true,
    lastEdited: node.lastEdited ?? '',
    children: node.children?.map((child) => transformNodes(child, repoId)),
  });

  /** 초기 레포 목록 로드 */
  const loadRepositories = async () => {
    try {
      setIsLoading(true);
      const data: ApiRepository[] = await githubService.getRepositories();
      const mapped: GithubNode[] = data.map((repo) => ({
        id: String(repo.repositoryId),
        name: repo.name,
        type: 'repo' as const,
        isPublic: repo.isPublic,
        lastEdited: new Date(repo.updatedAt).toLocaleDateString(),
        repositoryId: repo.repositoryId,
      }));
      setRepositories(mapped);
    } catch (err) {
      console.error('Failed to load repositories:', err);
    } finally {
      setIsLoading(false);
    }
  };

  /** 상세 파일 구조 로드 */
  const loadFileStructure = async (repo: GithubNode) => {
    if (!repo.repositoryId) return;

    try {
      setIsLoading(true);
      const data: ApiFileNode = await githubService.getRepositoryFiles(repo.repositoryId);
      const structured = transformNodes(data, repo.repositoryId);
      setFileStructure(structured);
      onNavigate(structured);
    } catch (err) {
      console.error('Failed to load file structure:', err);
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    loadRepositories();
  }, []);

  return {
    repositories,
    fileStructure,
    setFileStructure,
    isLoading,
    loadFileStructure,
    refresh: loadRepositories,
  };
};
