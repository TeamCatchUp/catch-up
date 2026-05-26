// 갤러리 index — registry 의 모든 entries 를 그룹별 타일 그리드로 노출.

import Link from 'next/link';

import {
  GALLERY_ENTRIES,
  GROUP_LABELS,
} from './_registry/entries';

export default function OriginalPanelGalleryIndexPage() {
  return (
    <div className="mx-auto flex max-w-5xl flex-col gap-8 px-8 py-10">
      <header className="flex flex-col gap-2">
        <h1 className="text-heading-large text-content-normal font-bold">원문 패널 갤러리</h1>
        <p className="text-body-medium text-content-alternative">
          ChannelTalk user_chat 원문 패널의 모든 컴포넌트를 상태·케이스별로 렌더합니다. 좌측 사이드바에서
          컴포넌트를 선택하거나 아래 타일을 클릭하세요. dev 전용 — 프로덕션 빌드에서 노출되지 않습니다.
        </p>
      </header>

      <div className="grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-3">
        {GALLERY_ENTRIES.map((entry) => (
          <Link
            key={entry.slug}
            href={`/original-panel/${entry.slug}`}
            className="bg-fill-strong border-edge-neutral hover:bg-fill-interaction-hover flex flex-col gap-1.5 rounded-xl border p-4 transition-colors"
          >
            <span className="text-body-xsmall text-content-assistive font-semibold tracking-wider uppercase">
              {GROUP_LABELS[entry.group]}
            </span>
            <span className="text-body-medium text-content-normal font-medium">{entry.title}</span>
            {entry.description && (
              <span className="text-body-small text-content-alternative">{entry.description}</span>
            )}
          </Link>
        ))}
      </div>
    </div>
  );
}
