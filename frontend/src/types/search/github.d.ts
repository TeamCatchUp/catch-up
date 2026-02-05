export interface GithubNode {
  id: string;
  name: string;
  type: 'repo' | 'tree' | 'blob';
  isPublic: boolean;
  lastEdited: string;
  children?: GithubNode[];
  /** API에서 반환되는 레포지토리 ID (repo 타입에서만 존재) */
  repositoryId?: number;
  /** 파일/폴더 경로 (tree, blob 타입에서 존재) */
  path?: string;
}
