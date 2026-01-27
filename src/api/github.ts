import api from '@/api/axios';

export const githubService = {
  // 레포지토리 목록 조회
  getRepositories: async () => {
    const res = await api.get('/api/github/read/repositories');
    return res.data;
  },

  // 레포지토리 내 파일 구조 조회
  getRepositoryFiles: async (repoId: number) => {
    const res = await api.get(`/api/github/read/repositories/${repoId}/files`);
    return res.data;
  },
};
