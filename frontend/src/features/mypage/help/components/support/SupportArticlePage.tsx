'use client';

import { notFound } from 'next/navigation';

import HelpArticleLayout from '@/features/mypage/help/components/article/HelpArticleLayout';
import { SUPPORTS } from '@/features/mypage/help/constants/supportData';
import { getAdjacentHelpArticleLinks } from '@/features/mypage/help/utils/helpArticleNavigation';

import Support1Content, { SUPPORT_1_SECTIONS } from './content/Support1Content';
import Support2Content, { SUPPORT_2_SECTIONS } from './content/Support2Content';
import Support3Content, { SUPPORT_3_SECTIONS } from './content/Support3Content';
import Support4Content, { SUPPORT_4_SECTIONS } from './content/Support4Content';

const SUPPORT_NAV_ITEMS = {
  1: SUPPORT_1_SECTIONS,
  2: SUPPORT_2_SECTIONS,
  3: SUPPORT_3_SECTIONS,
  4: SUPPORT_4_SECTIONS,
} as const;

const SUPPORT_CONTENT = {
  1: <Support1Content />,
  2: <Support2Content />,
  3: <Support3Content />,
  4: <Support4Content />,
} as const;

interface SupportArticlePageProps {
  supportId: number;
}

export default function SupportArticlePage({ supportId }: SupportArticlePageProps) {
  const support = SUPPORTS.find((item) => item.id === supportId);
  const content = SUPPORT_CONTENT[supportId as keyof typeof SUPPORT_CONTENT];

  if (!support || !content) {
    notFound();
  }

  const { prevItem, nextItem } = getAdjacentHelpArticleLinks(SUPPORTS, supportId, '/mypage/help/support');

  return (
    <HelpArticleLayout
      category={support.category}
      title={support.title}
      heroImage={support.heroImage}
      heroDarkImage={'heroDarkImage' in support ? support.heroDarkImage : undefined}
      navItems={SUPPORT_NAV_ITEMS[supportId as keyof typeof SUPPORT_NAV_ITEMS]}
      prevItem={prevItem}
      nextItem={nextItem}
    >
      {content}
    </HelpArticleLayout>
  );
}
