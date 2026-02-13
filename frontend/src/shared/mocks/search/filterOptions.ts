/**
 * Mock filter options for search/chat UI development
 * These are temporary test data used in FilterBar and RagInput components
 *
 * TODO: Replace with API data when backend provides:
 * - GET /api/v1/persons (for MOCK_PERSON_FILTER_OPTIONS)
 * - GET /api/v1/departments (for MOCK_DEPARTMENT_FILTER_OPTIONS)
 * - GET /api/v1/projects (for MOCK_PROJECT_FILTER_OPTIONS)
 */

export const MOCK_PERSON_FILTER_OPTIONS = [
  { name: '김준휘', position: '기획' },
  { name: '팀원B', position: '기획' },
  { name: '팀원E', position: '프론트엔드' },
  { name: '정성훈', position: '프론트엔드' },
  { name: '팀원C', position: '백엔드' },
  { name: '팀원A', position: '백엔드' },
  { name: '팀원F', position: '디자인' },
  { name: '조예원', position: '디자인' },
];

export const MOCK_DEPARTMENT_FILTER_OPTIONS = [
  { name: 'EngineeringTeam' },
  { name: 'SoccerTeam' },
];

export const MOCK_PROJECT_FILTER_OPTIONS = [
  { name: '미국진출프로젝트' },
  { name: '영국진출프로젝트2' },
  { name: '호국진출프로젝트3' },
  { name: '중국진출프로젝트4' },
];
