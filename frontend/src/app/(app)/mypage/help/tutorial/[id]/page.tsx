'use client';

import { use } from 'react';

import TutorialArticlePage from '@/features/mypage/help/components/tutorial/TutorialArticlePage';

interface TutorialPageProps {
  params: Promise<{ id: string }>;
}

export default function TutorialPage({ params }: TutorialPageProps) {
  const { id } = use(params);
  return <TutorialArticlePage tutorialId={Number(id)} />;
}
