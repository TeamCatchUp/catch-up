export interface GithubNode {
  id: string;
  name: string;
  type: 'repo' | 'tree' | 'blob';
  is_public: boolean;
  last_edited: string;
  children?: GithubNode[];
  /** API에서 반환되는 레포지토리 ID (repo 타입에서만 존재) */
  repository_id?: number;
  /** 파일/폴더 경로 (tree, blob 타입에서 존재) */
  path?: string;
}
