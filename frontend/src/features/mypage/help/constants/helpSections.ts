export const GUIDE_CARDS = [
  {
    id: 1,
    title: '검색 한 번으로 찾는 업무 정보',
    description: '정보를 찾는 시간,\n이제 일하는 시간으로 사용하세요.',
    image: '/image/help/light/search-work-info.jpg',
  },
  {
    id: 2,
    title: '원하는 답을 한 번에 얻는 비결',
    description: '질문이 구체적일수록 AI가 더 정확하게 대답해요.\n어떻게 질문을 작성하면 좋은지 알려드려요.',
    image: '/image/help/light/accurate-answers.jpg',
  },
  {
    id: 3,
    title: '정확도를 올리는 출처 확인 방법',
    description: '답변 뒤에 붙은 작은 번호를 누르면,\nAI가 참고한 자료의 출처로 바로 이동해요.',
    image: '/image/help/light/verify-sources.jpg',
  },
] as const;

export const SUPPORT_CARDS = [
  {
    id: 1,
    title: '자주 묻는 질문',
    tag: 'FAQ',
    description: '계정, 권한, 오류까지\n자주 나오는 질문만 모아두었어요.',
    image: '/image/help/light/faq.jpg',
  },
  {
    id: 2,
    title: '협업 툴 계정 관리',
    tag: '계정 매핑',
    description: '정확한 답변을 위해\n계정 연결 상태 확인해주세요.',
    image: '/image/help/light/integration.jpg',
  },
  {
    id: 3,
    title: '권한과 접근 문제',
    tag: '권한 요청',
    description: '자료가 보이지 않는다면,\n권한과 연동을 확인해 주세요.',
    image: '/image/help/light/permission.jpg',
  },
  {
    id: 4,
    title: '오류 및 장애',
    tag: '문제 해결',
    description: '문제가 생겼다면,\n빠르게 도와드릴게요.',
    image: '/image/help/light/error.jpg',
  },
] as const;

export const POLICY_ITEMS = [{ label: '이용약관' }, { label: '개인정보처리방침' }] as const;
