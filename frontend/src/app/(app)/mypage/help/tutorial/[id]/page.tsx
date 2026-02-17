'use client';

import { use } from 'react';
import Image from 'next/image';
import { notFound } from 'next/navigation';

import Tutorial1Content from '@/features/mypage/help/components/tutorial/Tutorial1Content';
import Tutorial2Content from '@/features/mypage/help/components/tutorial/Tutorial2Content';
import Tutorial3Content from '@/features/mypage/help/components/tutorial/Tutorial3Content';
import TutorialHeader from '@/features/mypage/help/components/tutorial/TutorialHeader';
import TutorialPagination from '@/features/mypage/help/components/tutorial/TutorialPagination';
import { TUTORIALS } from '@/features/mypage/help/constants/tutorialData';

interface TutorialPageProps {
  params: Promise<{ id: string }>;
}

export default function TutorialPage({ params }: TutorialPageProps) {
  const { id } = use(params);
  const tutorialId = Number(id);
  const tutorial = TUTORIALS.find((t) => t.id === tutorialId);

  if (!tutorial) {
    notFound();
  }

  return (
    <div className="flex flex-1 flex-col overflow-clip">
      <TutorialHeader prevLabel="도움말" prevHref="/mypage/help" currentLabel="튜토리얼" />

      <div className="flex flex-col items-center overflow-y-auto pt-10 pb-30">
        {/* Hero: 카테고리 + 제목 + 이미지 */}
        <div className="flex w-182 flex-col items-center gap-6">
          <div className="flex flex-col items-center gap-2.5 text-center">
            <span className="text-label-medium text-gray-50">[{tutorial.category}]</span>
            <h1 className="text-display-large text-gray-90">{tutorial.title}</h1>
          </div>
          {tutorial.heroImage && (
            <div className="relative aspect-1548/656 w-full overflow-hidden rounded-2xl">
              <Image src={tutorial.heroImage} alt={tutorial.title} fill className="object-cover" />
            </div>
          )}
        </div>

        {/* Content: 튜토리얼별 본문 */}
        <div className="mt-14 w-182">
          {tutorialId === 1 && <Tutorial1Content />}
          {tutorialId === 2 && <Tutorial2Content />}
          {tutorialId === 3 && <Tutorial3Content />}
        </div>

        {/* Pagination + 목록으로 */}
        <div className="mt-14">
          <TutorialPagination currentId={tutorialId} />
        </div>
      </div>
    </div>
  );
}
