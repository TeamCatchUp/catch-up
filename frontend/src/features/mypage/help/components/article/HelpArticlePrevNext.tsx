import Link from 'next/link';

import ArrowCircleRight from '@/public/icons/icon/arrow_circle_right.svg';
import { cn } from '@/shared/utils/cn';

import type { HelpArticleLinkItem } from '../../types/helpArticle';

interface HelpArticlePrevNextProps {
  prevItem?: HelpArticleLinkItem;
  nextItem?: HelpArticleLinkItem;
}

function ArticleNavCard({ item, direction }: { item: HelpArticleLinkItem; direction: 'prev' | 'next' }) {
  const isPrev = direction === 'prev';

  return (
    <Link
      href={item.href}
      className={cn(
        'border-line-normal-assistive bg-fill-normal-strong hover:bg-fill-normal-interaction-hover flex min-w-px flex-1 items-center gap-4 rounded-xl border p-3 transition-colors',
        !isPrev && 'justify-end',
      )}
    >
      {isPrev && <ArrowCircleRight className="text-icon-normal-alternative size-6 shrink-0 rotate-180" />}
      <span className={cn('flex min-w-0 flex-col gap-0.5', isPrev ? 'items-start' : 'items-end text-right')}>
        <span className="text-body-xsmall text-text-normal-alternative">{isPrev ? '이전' : '다음'}</span>
        <span className="text-heading-medium text-text-normal-normal max-w-full truncate">{item.title}</span>
      </span>
      {!isPrev && <ArrowCircleRight className="text-icon-normal-alternative size-6 shrink-0" />}
    </Link>
  );
}

export default function HelpArticlePrevNext({ prevItem, nextItem }: HelpArticlePrevNextProps) {
  return (
    <nav className="flex w-full gap-6 pt-5 lg:gap-20">
      {prevItem ? <ArticleNavCard item={prevItem} direction="prev" /> : <div aria-hidden className="min-w-px flex-1" />}
      {nextItem ? <ArticleNavCard item={nextItem} direction="next" /> : <div aria-hidden className="min-w-px flex-1" />}
    </nav>
  );
}
