export const JOB_LEVEL_OPTIONS = [
  { value: 'executive', label: '경영진' },
  { value: 'leader', label: '팀장' },
  { value: 'member', label: '팀원' },
] as const;

export const COMPANY_SIZE_OPTIONS = [
  { value: 'small', label: '1~5명' },
  { value: 'medium', label: '6~20명' },
  { value: 'large', label: '51~100명' },
  { value: 'enterprise', label: '100명 이상' },
] as const;

export const DEPARTMENT_OPTIONS = [
  // 제품 계열
  '부서K',
  '부서L',
  '부서M',
  '부서N',
  '부서J',
  '부서I',
  // 사업·영업 계열
  '부서A',
  '부서B',
  '부서C',
  '부서D',
  '부서E',
  // 마케팅·브랜드 계열
  '부서F',
  '부서G',
  '부서H',
] as const;
