import { useState, useEffect } from 'react';
import { githubService } from '@/api/github';

export const useGithubExplorer = (onNavigate: (node: any) => void) => {
  const [repositories, setRepositories] = useState<any[]>([]);
  const [fileStructure, setFileStructure] = useState<any>(null);
  const [isLoading, setIsLoading] = useState(false);

  // 데이터에 고유 ID 주입 (재귀 함수)
  const transformNodes = (node: any, repoId: number): any => ({
    ...node,
    id: node.path || `repo-${repoId}`,
    children: node.children?.map((child: any) => transformNodes(child, repoId)),
  });

  // 초기 레포 목록 로드
  const loadRepositories = async () => {
    try {
      setIsLoading(true);
      const data = await githubService.getRepositories();
      const mapped = data.map((repo: any) => ({
        ...repo,
        id: String(repo.repositoryId),
        type: 'repo',
        lastEdited: new Date(repo.updatedAt).toLocaleDateString(),
      }));
      setRepositories(mapped);
      console.log(mapped);
    } catch (err) {
      console.error(err);
    } finally {
      setIsLoading(false);
    }
  };

  // 상세 파일 구조 로드
  const loadFileStructure = async (repo: any) => {
    try {
      setIsLoading(true);
      const data = await githubService.getRepositoryFiles(repo.repositoryId);
      const structured = transformNodes(data, repo.repositoryId);
      setFileStructure(structured);
      onNavigate(structured);
      console.log(structured);
    } catch (err) {
      console.error(err);
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
