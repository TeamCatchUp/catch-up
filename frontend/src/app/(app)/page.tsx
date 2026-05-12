'use client';

// 홈 라우트. 실제 콘텐츠는 HomeContent에서 렌더하고 search 페이지도 동일 컴포넌트를 사용한다.

import HomeContent from '@/features/home/components/HomeContent';

export default function Home() {
  return <HomeContent />;
}
