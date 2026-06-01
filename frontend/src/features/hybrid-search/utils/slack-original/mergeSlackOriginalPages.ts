import type {
  SlackOriginalContentResponse,
  SlackUserMetadata,
} from '@/features/hybrid-search/types/slackOriginalApi';

function mergeUsersById(
  pages: SlackOriginalContentResponse[],
): Record<string, SlackUserMetadata> {
  return pages.reduce<Record<string, SlackUserMetadata>>((usersById, page) => {
    return {
      ...usersById,
      ...page.metadata.users_by_id,
    };
  }, {});
}

export function mergeSlackOriginalPages(
  pages: SlackOriginalContentResponse[],
): SlackOriginalContentResponse | null {
  const [firstPage] = pages;
  if (!firstPage) return null;

  const lastPage = pages[pages.length - 1] ?? firstPage;

  return {
    ...firstPage,
    items: pages.flatMap((page) => page.items),
    metadata: {
      ...firstPage.metadata,
      users_by_id: mergeUsersById(pages),
    },
    next_cursor: lastPage.next_cursor,
    fetched_at: lastPage.fetched_at,
  };
}
