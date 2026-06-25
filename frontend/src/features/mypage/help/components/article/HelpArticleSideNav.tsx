'use client';

import { useEffect, useState } from 'react';

import { cn } from '@/shared/utils/cn';

import type { HelpArticleNavItem } from '../../types/helpArticle';

interface HelpArticleSideNavProps {
  items: readonly HelpArticleNavItem[];
}

type ScrollTarget = HTMLElement | Window;

const ACTIVE_OFFSET = 120;

function isWindowScrollTarget(target: ScrollTarget): target is Window {
  return target === window;
}

function getScrollTarget(element: HTMLElement): ScrollTarget {
  let parent = element.parentElement;

  while (parent) {
    const { overflowY } = window.getComputedStyle(parent);
    const isScrollable = ['auto', 'scroll', 'overlay'].includes(overflowY);

    if (isScrollable && parent.scrollHeight > parent.clientHeight) {
      return parent;
    }

    parent = parent.parentElement;
  }

  return window;
}

function getInitialActiveId(items: readonly HelpArticleNavItem[]) {
  if (items.length === 0) return '';
  if (typeof window === 'undefined') return items[0].id;

  const hashId = window.location.hash.slice(1);
  return items.some((item) => item.id === hashId) ? hashId : items[0].id;
}

export default function HelpArticleSideNav({ items }: HelpArticleSideNavProps) {
  const [activeId, setActiveId] = useState(() => getInitialActiveId(items));

  useEffect(() => {
    const sectionElements = items
      .map((item) => document.getElementById(item.id))
      .filter((element): element is HTMLElement => element !== null);

    if (sectionElements.length === 0) return;

    const scrollTarget = getScrollTarget(sectionElements[0]);
    let animationFrameId = 0;

    const updateActiveId = () => {
      animationFrameId = 0;

      const rootTop = isWindowScrollTarget(scrollTarget) ? 0 : scrollTarget.getBoundingClientRect().top;
      const activationLine = rootTop + ACTIVE_OFFSET;
      let nextActiveId = sectionElements[0].id;

      for (const sectionElement of sectionElements) {
        const rect = sectionElement.getBoundingClientRect();

        if (rect.top <= activationLine) {
          nextActiveId = sectionElement.id;
          continue;
        }

        break;
      }

      setActiveId(nextActiveId);
    };

    const requestUpdate = () => {
      if (animationFrameId !== 0) return;
      animationFrameId = window.requestAnimationFrame(updateActiveId);
    };

    requestUpdate();

    scrollTarget.addEventListener('scroll', requestUpdate, { passive: true });
    window.addEventListener('resize', requestUpdate);
    window.addEventListener('hashchange', requestUpdate);

    return () => {
      if (animationFrameId !== 0) {
        window.cancelAnimationFrame(animationFrameId);
      }

      scrollTarget.removeEventListener('scroll', requestUpdate);
      window.removeEventListener('resize', requestUpdate);
      window.removeEventListener('hashchange', requestUpdate);
    };
  }, [items]);

  if (items.length === 0) return null;

  return (
    <aside className="sticky top-9 hidden h-fit max-h-[calc(100vh-72px)] shrink-0 self-start overflow-x-hidden overflow-y-auto rounded-2xl p-4 lg:block">
      <nav aria-label="본문 목차">
        <ul className="flex flex-col">
          {items.map((item) => {
            const isActive = item.id === activeId;

            return (
              <li key={item.id}>
                <a
                  href={`#${item.id}`}
                  title={item.title}
                  aria-current={isActive ? 'location' : undefined}
                  onClick={() => setActiveId(item.id)}
                  className={cn(
                    'text-heading-small flex py-2.5 pr-3 pl-4',
                    isActive
                      ? 'border-line-primary-strong bg-fill-primary-normal-neutral text-text-primary-normal w-52.5 border-l-2'
                      : 'border-line-normal-normal text-text-normal-alternative hover:bg-fill-normal-interaction-hover w-52.25 border-l transition-colors',
                  )}
                >
                  <span className="block w-45 truncate">{item.title}</span>
                </a>
              </li>
            );
          })}
        </ul>
      </nav>
    </aside>
  );
}
