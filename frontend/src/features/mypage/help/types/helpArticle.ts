import type { ReactNode } from 'react';

export interface HelpArticleNavItem {
  id: string;
  title: string;
}

export interface HelpArticleLinkItem {
  title: string;
  href: string;
}

export interface HelpArticleLayoutProps {
  category: string;
  title: string;
  heroImage?: string;
  navItems: readonly HelpArticleNavItem[];
  prevItem?: HelpArticleLinkItem;
  nextItem?: HelpArticleLinkItem;
  children: ReactNode;
}
