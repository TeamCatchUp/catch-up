import { useEffect, useMemo, useRef } from 'react';

import DateIndicator from '@/features/hybrid-search/components/original/shared/DateIndicator';
import type { SlackOriginalContentResponse } from '@/features/hybrid-search/types/slackOriginalApi';
import { mergeSlackOriginalPages } from '@/features/hybrid-search/utils/slackOriginal/mergeSlackOriginalPages';
import { parseSlackOriginalThread } from '@/features/hybrid-search/utils/slackOriginal/parseSlackOriginal';

import SlackThreadHeader from './header/SlackThreadHeader';
import SlackMessageItem from './message/SlackMessageItem';

interface SlackOriginalPanelContentProps {
  pages: SlackOriginalContentResponse[];
  hasNextPage: boolean;
  isFetchingNextPage: boolean;
  onLoadNextPage: () => void;
}

export default function SlackOriginalPanelContent({
  pages,
  hasNextPage,
  isFetchingNextPage,
  onLoadNextPage,
}: SlackOriginalPanelContentProps) {
  const scrollRootRef = useRef<HTMLDivElement>(null);
  const loadMoreRef = useRef<HTMLDivElement>(null);
  const mergedResponse = useMemo(() => mergeSlackOriginalPages(pages), [pages]);

  useEffect(() => {
    const target = loadMoreRef.current;
    const root = scrollRootRef.current;
    if (!target || !root || !hasNextPage || isFetchingNextPage) return;

    const observer = new IntersectionObserver(
      ([entry]) => {
        if (entry?.isIntersecting) onLoadNextPage();
      },
      { root, rootMargin: '120px 0px' },
    );

    observer.observe(target);
    return () => observer.disconnect();
  }, [hasNextPage, isFetchingNextPage, onLoadNextPage]);

  if (!mergedResponse) return null;

  const thread = parseSlackOriginalThread(mergedResponse);
  const [parent, ...replies] = thread.messages;

  return (
    <div className="border-edge-normal flex w-105.75 max-w-full flex-col items-start justify-center gap-3 border-l py-4 pl-6">
      <SlackThreadHeader channelName={thread.channelName} participantNames={thread.participantNames} />
      <div
        ref={scrollRootRef}
        className="custom-scrollbar flex w-99.75 max-w-full flex-col items-start gap-5 overflow-y-auto pb-5"
      >
        {parent?.dateKey && <DateIndicator date={parent.dateKey} />}
        {parent && <SlackMessageItem message={parent} />}
        <div className="flex h-5 w-full items-center gap-3 px-3">
          <span className="text-body-xsmall text-content-alternative shrink-0 font-medium">
            {thread.commentCount}개의 댓글
          </span>
          <span aria-hidden className="bg-edge-neutral h-px min-w-0 flex-1" />
        </div>
        {replies.map((message) => (
          <SlackMessageItem key={message.id} message={message} />
        ))}
        {hasNextPage && <div ref={loadMoreRef} aria-hidden className="h-1 w-full" />}
      </div>
    </div>
  );
}
