'use client';

// Figma 13413:53651 — text 2줄 + chat2 아이콘 버튼.
// 컨테이너 py-50(200px), gap-2(8px). 텍스트 그룹 gap-1(4px). 버튼 h-8 rounded-full px-1.5 py-1 gap-1.

import { useRouter } from 'next/navigation';

import Chat2 from '@/public/icons/icon/chat2.svg';

export default function ResultEmptyState() {
  const router = useRouter();

  return (
    <div className="flex flex-col items-center gap-2 py-50">
      <div className="text-heading-small flex flex-col items-center gap-1 font-semibold">
        <p className="text-content-alternative">문서에서는 찾지 못했어요.</p>
        <p className="text-content-assistive">다른 키워드로 검색하거나 AI에게 직접 물어보세요</p>
      </div>
      <button
        type="button"
        onClick={() => router.push('/search')}
        className="text-content-primary hover:bg-fill-primary-interaction-hover-assistive flex h-8 cursor-pointer items-center gap-1 rounded-full px-1.5 py-1 transition-colors"
      >
        <Chat2 className="text-icon-primary h-5 w-5" />
        <span className="text-body-small font-medium">캐치스턴트에게 질문하기</span>
      </button>
    </div>
  );
}
