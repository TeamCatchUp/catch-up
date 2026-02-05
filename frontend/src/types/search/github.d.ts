export interface GithubNode {
  id: string;
  name: string;
  type: 'repo' | 'tree' | 'blob';
  isPublic: boolean;
  lastEdited: string;
  children?: GithubNode[];
}
