'use client';

import { notFound } from 'next/navigation';

import HelpArticleLayout from '@/features/mypage/help/components/article/HelpArticleLayout';
import { TUTORIALS } from '@/features/mypage/help/constants/tutorialData';
import { getAdjacentHelpArticleLinks } from '@/features/mypage/help/utils/helpArticleNavigation';

import Tutorial1Content, { TUTORIAL_1_SECTIONS } from './content/Tutorial1Content';
import Tutorial2Content, { TUTORIAL_2_SECTIONS } from './content/Tutorial2Content';
import Tutorial3Content, { TUTORIAL_3_SECTIONS } from './content/Tutorial3Content';
import Tutorial4Content, { TUTORIAL_4_SECTIONS } from './content/Tutorial4Content';

const TUTORIAL_NAV_ITEMS = {
  1: TUTORIAL_1_SECTIONS,
  2: TUTORIAL_2_SECTIONS,
  3: TUTORIAL_3_SECTIONS,
  4: TUTORIAL_4_SECTIONS,
} as const;

const TUTORIAL_CONTENT = {
  1: <Tutorial1Content />,
  2: <Tutorial2Content />,
  3: <Tutorial3Content />,
  4: <Tutorial4Content />,
} as const;

interface TutorialArticlePageProps {
  tutorialId: number;
}

export default function TutorialArticlePage({ tutorialId }: TutorialArticlePageProps) {
  const tutorial = TUTORIALS.find((item) => item.id === tutorialId);
  const content = TUTORIAL_CONTENT[tutorialId as keyof typeof TUTORIAL_CONTENT];

  if (!tutorial || !content) {
    notFound();
  }

  const { prevItem, nextItem } = getAdjacentHelpArticleLinks(TUTORIALS, tutorialId, '/mypage/help/tutorial');

  return (
    <HelpArticleLayout
      category={tutorial.category}
      title={tutorial.title}
      heroImage={'heroImage' in tutorial ? tutorial.heroImage : undefined}
      navItems={TUTORIAL_NAV_ITEMS[tutorialId as keyof typeof TUTORIAL_NAV_ITEMS]}
      prevItem={prevItem}
      nextItem={nextItem}
    >
      {content}
    </HelpArticleLayout>
  );
}
