'use client';

// 사이드바 단일 nav 항목 — 활성/비활성 스타일 분기.

import Link from 'next/link';

import type { GalleryEntry } from '../_registry/entries';

interface SidebarLinkProps {
  entry: GalleryEntry;
  active: boolean;
}

export default function SidebarLink({ entry, active }: SidebarLinkProps) {
  const className = active
    ? 'bg-fill-interaction-pressed text-content-normal text-body-small block rounded-md px-2 py-1.5 font-medium'
    : 'text-content-alternative hover:bg-fill-interaction-hover hover:text-content-normal text-body-small block rounded-md px-2 py-1.5';

  return (
    <Link href={`/original-panel/${entry.slug}`} className={className}>
      {entry.title}
    </Link>
  );
}
