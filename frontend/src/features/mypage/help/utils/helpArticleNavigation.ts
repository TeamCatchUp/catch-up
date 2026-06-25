import type { HelpArticleLinkItem } from '../types/helpArticle';

interface ArticleListItem {
  id: number;
  title: string;
}

export function getAdjacentHelpArticleLinks(
  items: readonly ArticleListItem[],
  currentId: number,
  basePath: string,
): { prevItem?: HelpArticleLinkItem; nextItem?: HelpArticleLinkItem } {
  const currentIndex = items.findIndex((item) => item.id === currentId);
  if (currentIndex === -1) return {};

  const prev = items[currentIndex - 1];
  const next = items[currentIndex + 1];

  return {
    prevItem: prev ? { title: prev.title, href: `${basePath}/${prev.id}` } : undefined,
    nextItem: next ? { title: next.title, href: `${basePath}/${next.id}` } : undefined,
  };
}
