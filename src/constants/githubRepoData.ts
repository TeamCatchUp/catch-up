export interface GithubNode {
  id: string;
  name: string;
  type: 'repo' | 'folder' | 'file';
  isPublic: boolean;
  lastEdited: string;
  children?: GithubNode[];
}

export const GITHUB_MOCK_DATA: GithubNode[] = [
  {
    id: 'repo-1',
    name: 'front-end-monorepo',
    type: 'repo',
    isPublic: false,
    lastEdited: '3일전',
    children: [
      {
        id: 'folder-1',
        name: 'packages',
        type: 'folder',
        isPublic: false,
        lastEdited: '3일전',
        children: [
          {
            id: 'file-1',
            name: 'ui-kit',
            type: 'folder',
            isPublic: false,
            lastEdited: '3일전',
            children: [
              { id: 'file-6', name: 'Dockerfile', type: 'file', isPublic: true, lastEdited: '3일전' },
              { id: 'file-5', name: 'Dockerfile', type: 'file', isPublic: true, lastEdited: '3일전' },
            ],
          },
          { id: 'file-2', name: 'utils.ts', type: 'file', isPublic: false, lastEdited: '3일전' },
        ],
      },
      { id: 'file-3', name: 'package.json', type: 'file', isPublic: false, lastEdited: '3일전' },
    ],
  },
  {
    id: 'repo-2',
    name: 'backend-api-server',
    type: 'repo',
    isPublic: true,
    lastEdited: '3일전',
    children: [
      { id: 'folder-2', name: 'src', type: 'folder', isPublic: true, lastEdited: '3일전', children: [] },
      { id: 'file-8', name: 'Dockerfile', type: 'file', isPublic: true, lastEdited: '3일전' },
    ],
  },
  {
    id: 'repo-3',
    name: 'tndnd-api-server',
    type: 'repo',
    isPublic: true,
    lastEdited: '3일전',
    children: [
      { id: 'folder-2', name: 'src', type: 'folder', isPublic: true, lastEdited: '3일전', children: [] },
      { id: 'file-7', name: 'Dockerfile', type: 'file', isPublic: true, lastEdited: '3일전' },
    ],
  },
];
