'use client';

import { use } from 'react';

import SupportArticlePage from '@/features/mypage/help/components/support/SupportArticlePage';

interface SupportPageProps {
  params: Promise<{ id: string }>;
}

export default function SupportPage({ params }: SupportPageProps) {
  const { id } = use(params);
  return <SupportArticlePage supportId={Number(id)} />;
}
