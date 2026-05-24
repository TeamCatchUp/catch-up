'use client';

// 원문 메시지의 첨부 파일 한 줄. file 콘텐츠에서 files[] 각 요소를 렌더.
// file.url 이 안전하면 새 탭 다운로드 링크로, 아니면 비링크로 표시.

import type { OriginalFile } from '@/features/hybrid-search/types/originalApi';
import { formatFileSize } from '@/features/hybrid-search/utils/format/formatFileSize';
import { formatFileType } from '@/features/hybrid-search/utils/format/formatFileType';
import FileIcon from '@/public/icons/icon/file_filled.svg';
import type { SourceTypeApi } from '@/shared/types/sourceApi';
import { isSafeUrl } from '@/shared/utils/isSafeUrl';

interface FileRowProps {
  file: OriginalFile;
  // Task 3 에서 mutation 호출에 사용 — 현 시점에선 시그니처만.
  connector: SourceTypeApi;
  documentId: string;
}

export default function FileRow({ file, connector, documentId }: FileRowProps) {
  // Task 3 에서 사용 — 일단 unused-var 회피.
  void connector;
  void documentId;
  const name = file.name?.trim() ? file.name : '이름 없음';
  const sizeLabel = formatFileSize(file.size);
  const typeLabel = formatFileType(name, file.content_type);
  const isLink = isSafeUrl(file.url);

  const meta = [sizeLabel, typeLabel].filter(Boolean).join(' ∙ ');

  const inner = (
    <>
      <span className="bg-fill-normal flex shrink-0 items-center justify-center rounded-lg p-2">
        <FileIcon className="text-icon-primary-assistive size-7" />
      </span>
      <span className="flex min-w-0 flex-1 flex-col gap-0.5">
        <span className="text-body-small text-content-neutral truncate">{name}</span>
        {meta && <span className="text-body-xsmall text-content-assistive truncate">{meta}</span>}
      </span>
    </>
  );

  const className =
    'bg-fill-strong border-edge-neutral flex w-full items-center gap-2.5 rounded-lg border p-2 text-left';

  if (isLink) {
    return (
      <a
        href={file.url}
        target="_blank"
        rel="noopener noreferrer"
        className={className}
      >
        {inner}
      </a>
    );
  }

  return <div className={className}>{inner}</div>;
}
