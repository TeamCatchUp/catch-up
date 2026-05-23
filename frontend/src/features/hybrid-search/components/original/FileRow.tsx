'use client';

// 원문 메시지의 첨부 파일 한 줄. file 콘텐츠에서 files[] 각 요소를 렌더.
// file.url 이 안전하면 새 탭 다운로드 링크로, 아니면 비링크로 표시.

import type { ReactNode } from 'react';

import type { OriginalFile } from '@/features/hybrid-search/types/originalApi';
import FileIcon from '@/public/icons/icon/file_filled.svg';
import { isSafeUrl } from '@/shared/utils/isSafeUrl';

interface FileRowProps {
  file: OriginalFile;
}

const FILE_SIZE_UNITS = ['B', 'KB', 'MB', 'GB', 'TB'] as const;

// 바이트 → 사람이 읽는 크기 (예: 347.3KB). B 단위는 소수점 없이.
function formatFileSize(bytes: number | undefined): string | null {
  if (bytes == null || !Number.isFinite(bytes) || bytes < 0) return null;

  let size = bytes;
  let unitIndex = 0;
  while (size >= 1024 && unitIndex < FILE_SIZE_UNITS.length - 1) {
    size /= 1024;
    unitIndex += 1;
  }

  const rounded = unitIndex === 0 ? String(size) : size.toFixed(1);
  return `${rounded}${FILE_SIZE_UNITS[unitIndex]}`;
}

// 파일 확장자 우선, 없으면 MIME 서브타입을 짧은 타입 라벨로 (예: pdf).
function formatFileType(name: string, contentType: string | undefined): string | null {
  const extMatch = /\.([a-z0-9]+)$/i.exec(name);
  if (extMatch) return extMatch[1].toLowerCase();

  const mime = contentType?.trim();
  if (!mime) return null;
  const subtype = mime.split('/')[1]?.split('+')[0];
  return subtype ? subtype.toLowerCase() : null;
}

export default function FileRow({ file }: FileRowProps) {
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
        {inner as ReactNode}
      </a>
    );
  }

  return <div className={className}>{inner}</div>;
}
