'use client';

// 좌측 네비. 그룹별 헤더 + 항목 리스트. 활성 항목은 pathname 마지막 segment 매칭.

import Link from 'next/link';
import { usePathname } from 'next/navigation';

import {
  GROUP_LABELS,
  GROUP_ORDER,
  GROUPED_ENTRIES,
} from '../_registry/entries';
import SidebarLink from './SidebarLink';

export default function Sidebar() {
  const pathname = usePathname();
  const activeSlug = pathname.split('/').filter(Boolean).pop() ?? '';

  return (
    <nav className="border-edge-neutral bg-fill-strong sticky top-0 flex h-screen w-64 shrink-0 flex-col gap-6 overflow-y-auto border-r p-4">
      <Link
        href="/original-panel"
        className="text-heading-small text-content-normal font-bold"
      >
        원문 패널 갤러리
      </Link>
      {GROUP_ORDER.map((group) => (
        <div key={group} className="flex flex-col gap-1">
          <span className="text-body-xsmall text-content-assistive px-2 font-semibold tracking-wider uppercase">
            {GROUP_LABELS[group]}
          </span>
          {GROUPED_ENTRIES[group].map((entry) => (
            <SidebarLink
              key={entry.slug}
              entry={entry}
              active={activeSlug === entry.slug}
            />
          ))}
        </div>
      ))}
    </nav>
  );
}
