import type { ReactNode } from 'react';

export interface AdminGuideStep {
  title: string[];
  image: string;
  body: ReactNode;
}

export const ADMIN_GUIDE_STEPS: AdminGuideStep[] = [
  {
    title: ['찾지 말고, 질문하세요', '흩어진 기록은 Catch Up이 찾아드릴게요.'],
    image: '/image/admin-guide/admin-guide-step-1.jpg',
    body: '근거가 된 출처를 함께 보여주고,\n클릭 한 번으로 원문까지 확인할 수 있어요.',
  },
  {
    title: ['사내 기록을 가져오려면', '협업 툴 연결이 필요해요'],
    image: '/image/admin-guide/admin-guide-step-2.jpg',
    body: '사용하는 협업 툴만 연결해두면 Catch Up이 필요한 기록을 알아서 모아와요.\n커넥터별 안내대로 한 번만 따라가면 끝이에요.',
  },
  {
    title: ['정확히 답하려면', "'계정 매핑'이 필요해요"],
    image: '/image/admin-guide/admin-guide-step-3.jpg',
    body: null, // Step 3 has custom body rendering
  },
  {
    title: ['그럼 바로 시작할까요?'],
    image: '/image/admin-guide/admin-guide-step-4.jpg',
    body: '나머진 Catch Up이 도와드릴게요.',
  },
];

export const ADMIN_GUIDE_STORAGE_KEY = 'catchup:admin-guide-dismissed';

export const TOTAL_STEPS = ADMIN_GUIDE_STEPS.length;
