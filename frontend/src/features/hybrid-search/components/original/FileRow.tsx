'use client';

// 원문 메시지의 첨부 파일 한 줄. file 콘텐츠에서 files[] 각 요소를 렌더.
// 클릭 시 backend mutation 호출 → presigned URL 받아 새 탭에서 다운로드/미리보기.
// 팝업 차단 회피: 클릭 동기 시점에 about:blank 새 탭을 미리 열고 onSuccess 에서 location 갱신.
// file_key 없는 파일은 비링크 div 유지.

import { useMutation } from '@tanstack/react-query';
import { toast } from 'sonner';

import { originalFileUrlMutations } from '@/features/hybrid-search/queries/originalFileUrl.mutations';
import type { OriginalFile } from '@/features/hybrid-search/types/originalApi';
import { formatFileSize } from '@/features/hybrid-search/utils/format/formatFileSize';
import { formatFileType } from '@/features/hybrid-search/utils/format/formatFileType';
import FileIcon from '@/public/icons/icon/file_filled.svg';
import { parseApiError } from '@/shared/api/errors';
import type { SourceTypeApi } from '@/shared/types/sourceApi';

interface FileRowProps {
  file: OriginalFile;
  connector: SourceTypeApi;
  documentId: string;
}

export default function FileRow({ file, connector, documentId }: FileRowProps) {
  const { mutate, isPending } = useMutation(originalFileUrlMutations.download());

  const name = file.name?.trim() ? file.name : '이름 없음';
  const sizeLabel = formatFileSize(file.size);
  const typeLabel = formatFileType(name, file.content_type);
  const meta = [sizeLabel, typeLabel].filter(Boolean).join(' ∙ ');
  const fileKey = file.file_key;

  const baseClass =
    'bg-fill-strong border-edge-neutral flex w-full items-center gap-2.5 rounded-lg border p-2 text-left';

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

  // file_key 없는 파일은 다운로드 불가 — 정적 표시만 (백엔드 min_length:1 검증 회피).
  if (!fileKey) {
    return <div className={baseClass}>{inner}</div>;
  }

  const handleClick = () => {
    if (isPending) return;
    const win = window.open('about:blank', '_blank'); // 동기 — 팝업 차단 통과

    mutate(
      { connector, document_id: documentId, file_key: fileKey },
      {
        onSuccess: (res) => {
          const url = res.data.url;
          if (!url) {
            win?.close();
            toast.error('파일을 불러올 수 없습니다');
            return;
          }
          if (win) win.location.href = url;
        },
        onError: (error) => {
          win?.close();
          toast.error(parseApiError(error).message);
        },
      },
    );
  };

  return (
    <button
      type="button"
      onClick={handleClick}
      disabled={isPending}
      aria-disabled={isPending}
      className={`${baseClass} ${isPending ? 'pointer-events-none opacity-50' : ''}`.trim()}
    >
      {inner}
    </button>
  );
}
