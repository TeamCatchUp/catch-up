export interface UserGuideStep {
  title: string[];
  image: string;
  body: string;
}

export const USER_GUIDE_STEPS: UserGuideStep[] = [
  {
    title: ['흩어져 있는 업무 기록들,', '이제는 한번에 확인할 수 있어요.'],
    image: '/image/user-guide/user-guide-step-1.jpg',
    body: '어디에 무엇이 있는지 기억할 필요 없습니다.\n\nJira, Github, Slack 등 여러 툴에 흩어진 정보를.\nCatch Up이 한 번에 정리해 알려드려요.',
  },
  {
    title: ['정보의 정확한 출처와', "'인용 이유'까지 같이 보여줘요"],
    image: '/image/user-guide/user-guide-step-2.jpg',
    body: '답변에 쓰인 정보의 출처를 바로 확인할 수 있어요.\n그리고 왜 이 출처를 사용했는지, 그 이유도 함께 설명합니다.',
  },
  {
    title: ['질문이 떠오르지 않는다면', '상황별 맞춤 프롬프트로 시작해요.'],
    image: '/image/user-guide/user-guide-step-3.jpg',
    body: '바로 활용할 수 있는 상황별 맞춤 템플릿을 드려요.\n원하는 답이 나오도록 질문을 쉽게 다듬어줍니다.',
  },
  {
    title: ['그럼 바로 시작할까요?'],
    image: '/image/user-guide/user-guide-step-4.jpg',
    body: '나머진 Catch Up이 도와드릴게요.',
  },
];

export const USER_GUIDE_STORAGE_KEY = 'catchup:user-guide-dismissed';

export const USER_GUIDE_TOTAL_STEPS = USER_GUIDE_STEPS.length;
