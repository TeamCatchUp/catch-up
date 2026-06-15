'use client';

import { use } from 'react';
import Image from 'next/image';
import { notFound } from 'next/navigation';

import Support1Content from '@/features/mypage/help/components/support/Support1Content';
import Support2Content from '@/features/mypage/help/components/support/Support2Content';
import Support3Content from '@/features/mypage/help/components/support/Support3Content';
import Support4Content from '@/features/mypage/help/components/support/Support4Content';
import SupportPagination from '@/features/mypage/help/components/support/SupportPagination';
import TutorialHeader from '@/features/mypage/help/components/tutorial/TutorialHeader';
import { SUPPORTS } from '@/features/mypage/help/constants/supportData';

interface SupportPageProps {
  params: Promise<{ id: string }>;
}

export default function SupportPage({ params }: SupportPageProps) {
  const { id } = use(params);
  const supportId = Number(id);
  const support = SUPPORTS.find((s) => s.id === supportId);

  if (!support) {
    notFound();
  }

  return (
    <div className="flex flex-1 flex-col overflow-clip">
      <TutorialHeader prevLabel="도움말" prevHref="/mypage/help" currentLabel={support.title} />

      <div className="flex flex-col items-center overflow-y-auto pt-10 pb-30">
        {/* Hero: 카테고리 + 제목 + 이미지 */}
        <div className="flex w-182 flex-col items-center gap-6">
          <div className="flex flex-col items-center gap-2.5 text-center">
            <span className="text-label-medium text-text-normal-alternative">[{support.category}]</span>
            <h1 className="text-display-large text-text-normal-strong">{support.title}</h1>
          </div>
          {support.heroImage && (
            <div className="relative aspect-1548/656 w-full overflow-hidden rounded-2xl">
              <Image src={support.heroImage} alt={support.title} fill className="object-cover" />
            </div>
          )}
        </div>

        {/* Content: 페이지별 본문 */}
        <div className="mt-14 w-182">
          {supportId === 1 && <Support1Content />}
          {supportId === 2 && <Support2Content />}
          {supportId === 3 && <Support3Content />}
          {supportId === 4 && <Support4Content />}
        </div>

        {/* Pagination + 목록으로 */}
        <div className="mt-14">
          <SupportPagination currentId={supportId} />
        </div>
      </div>
    </div>
  );
}
