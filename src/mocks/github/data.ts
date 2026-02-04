export interface RepositoryResponse {
  repositoryId: number;
  name: string;
  fullName: string;
  isPublic: boolean;
  updatedAt: string;
}

export const MOCK_REPOSITORIES: RepositoryResponse[] = [
  {
    repositoryId: 1,
    name: 'CatchUp-FE',
    fullName: 'TeamCatchUp/CatchUp-FE',
    isPublic: false,
    updatedAt: '2024-01-15T10:30:00Z',
  },
  {
    repositoryId: 2,
    name: 'CatchUp-BE',
    fullName: 'TeamCatchUp/CatchUp-BE',
    isPublic: false,
    updatedAt: '2024-01-14T15:20:00Z',
  },
  {
    repositoryId: 3,
    name: 'CatchUp-AI',
    fullName: 'TeamCatchUp/CatchUp-AI',
    isPublic: false,
    updatedAt: '2024-01-13T09:00:00Z',
  },
];

export interface FileTreeNode {
  name: string;
  path: string;
  type: 'tree' | 'blob';
  children?: FileTreeNode[];
}

export const MOCK_FILE_TREES: Record<number, FileTreeNode> = {
  1: {
    name: 'CatchUp-FE',
    path: '',
    type: 'tree',
    children: [
      {
        name: 'src',
        path: 'src',
        type: 'tree',
        children: [
          {
            name: 'components',
            path: 'src/components',
            type: 'tree',
            children: [
              { name: 'Header.tsx', path: 'src/components/Header.tsx', type: 'blob' },
              { name: 'Footer.tsx', path: 'src/components/Footer.tsx', type: 'blob' },
            ],
          },
          {
            name: 'pages',
            path: 'src/pages',
            type: 'tree',
            children: [
              { name: 'index.tsx', path: 'src/pages/index.tsx', type: 'blob' },
              { name: 'login.tsx', path: 'src/pages/login.tsx', type: 'blob' },
            ],
          },
          { name: 'App.tsx', path: 'src/App.tsx', type: 'blob' },
          { name: 'main.tsx', path: 'src/main.tsx', type: 'blob' },
        ],
      },
      { name: 'package.json', path: 'package.json', type: 'blob' },
      { name: 'tsconfig.json', path: 'tsconfig.json', type: 'blob' },
      { name: 'README.md', path: 'README.md', type: 'blob' },
    ],
  },
  2: {
    name: 'CatchUp-BE',
    path: '',
    type: 'tree',
    children: [
      {
        name: 'src',
        path: 'src',
        type: 'tree',
        children: [
          {
            name: 'main',
            path: 'src/main',
            type: 'tree',
            children: [
              {
                name: 'java',
                path: 'src/main/java',
                type: 'tree',
                children: [
                  { name: 'AuthController.java', path: 'src/main/java/AuthController.java', type: 'blob' },
                  { name: 'ChatController.java', path: 'src/main/java/ChatController.java', type: 'blob' },
                ],
              },
            ],
          },
        ],
      },
      { name: 'build.gradle', path: 'build.gradle', type: 'blob' },
      { name: 'README.md', path: 'README.md', type: 'blob' },
    ],
  },
  3: {
    name: 'CatchUp-AI',
    path: '',
    type: 'tree',
    children: [
      {
        name: 'src',
        path: 'src',
        type: 'tree',
        children: [
          { name: 'main.py', path: 'src/main.py', type: 'blob' },
          { name: 'rag.py', path: 'src/rag.py', type: 'blob' },
        ],
      },
      { name: 'requirements.txt', path: 'requirements.txt', type: 'blob' },
      { name: 'README.md', path: 'README.md', type: 'blob' },
    ],
  },
};

export const DEFAULT_FILE_TREE: FileTreeNode = {
  name: 'unknown',
  path: '',
  type: 'tree',
  children: [],
};
