import type { SlackOriginalContentResponse } from '@/features/hybrid-search/types/slackOriginalApi';

export function mergeSlackOriginalPages(
  pages: SlackOriginalContentResponse[],
): SlackOriginalContentResponse | null {
  const [firstPage] = pages;
  if (!firstPage) return null;

  const lastPage = pages[pages.length - 1] ?? firstPage;

  return {
    ...firstPage,
    items: pages.flatMap((page) => page.items),
    next_cursor: lastPage.next_cursor,
    fetched_at: lastPage.fetched_at,
  };
}
