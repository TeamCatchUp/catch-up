import { cn } from '@/shared/utils/cn';

import type { HelpArticleNavItem } from '../../types/helpArticle';

interface HelpArticleSideNavProps {
  items: readonly HelpArticleNavItem[];
}

export default function HelpArticleSideNav({ items }: HelpArticleSideNavProps) {
  if (items.length === 0) return null;

  return (
    <aside className="sticky top-9 hidden max-h-[calc(100vh-72px)] shrink-0 self-start overflow-x-hidden overflow-y-auto rounded-2xl p-4 lg:block">
      <nav aria-label="본문 목차">
        <ul className="flex flex-col">
          {items.map((item, index) => (
            <li key={item.id}>
              <a
                href={`#${item.id}`}
                title={item.title}
                className={cn(
                  'text-heading-small flex py-2.5 pr-3 pl-4',
                  index === 0
                    ? 'border-line-primary-strong bg-fill-primary-normal-neutral text-text-primary-normal w-[210px] border-l-2'
                    : 'border-line-normal-normal text-text-normal-alternative hover:bg-fill-normal-interaction-hover w-[209px] border-l transition-colors',
                )}
              >
                <span className="block w-[180px] truncate">{item.title}</span>
              </a>
            </li>
          ))}
        </ul>
      </nav>
    </aside>
  );
}
