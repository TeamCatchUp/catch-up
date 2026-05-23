// 컴포넌트 단위 sub-route — slug 로 registry/renderer 조회해 렌더.

import { notFound } from 'next/navigation';

import { GALLERY_ENTRIES } from '../_registry/entries';
import EntryRenderer from '../_registry/render';

export function generateStaticParams() {
  return GALLERY_ENTRIES.map((entry) => ({ slug: entry.slug }));
}

interface PageProps {
  params: Promise<{ slug: string }>;
}

export default async function OriginalPanelEntryPage({ params }: PageProps) {
  const { slug } = await params;
  const entry = GALLERY_ENTRIES.find((e) => e.slug === slug);
  if (!entry) notFound();

  return (
    <div className="mx-auto flex max-w-4xl flex-col gap-8 px-8 py-10">
      <header className="flex flex-col gap-2">
        <h1 className="text-heading-large text-content-normal font-bold">{entry.title}</h1>
        {entry.description && (
          <p className="text-body-medium text-content-alternative">{entry.description}</p>
        )}
      </header>
      <div className="flex flex-col gap-4">
        <EntryRenderer slug={entry.slug} />
      </div>
    </div>
  );
}
