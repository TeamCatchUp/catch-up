'use client';

// Figma 13385:55955 — 정적 illustration 대신 chat source panel에서 쓰는 lottie 사용.
// 컨테이너 py-50(200px), gap-4(16px). 텍스트 두 줄 사이 gap-2(8px).

import Lottie from 'lottie-react';

import ragSourceLoading from '@/public/lottie/rag-source-loading.json';

export default function ResultLoadingState() {
  return (
    <div className="flex flex-col items-center gap-4 py-50">
      <Lottie animationData={ragSourceLoading} loop className="h-23 w-28.75" />
      <div className="flex flex-col items-center gap-2">
        <p className="text-heading-medium text-content-neutral font-semibold">문서를 찾고 있어요</p>
        <p className="text-body-small text-content-alternative font-medium">필요한 문서를 불러오고 있어요</p>
      </div>
    </div>
  );
}
