'use client';

// 원문 메시지의 첨부 파일 한 줄. file 콘텐츠에서 files[] 각 요소를 렌더.
// 클릭 시 backend mutation 호출 → presigned URL 받아 새 탭에서 다운로드/미리보기.
//
// 팝업 차단 회피: 클릭 동기 시점에 about:blank 새 탭을 열고 onSuccess 에서 location 갱신.
// noopener 옵션 미사용 — Chrome 88+ 는 noopener 시 window.open 이 null 반환 → onSuccess 의
// anchor.click() fallback 이 비동기 컨텍스트라 popup blocker 가 다시 차단되는 문제 회피.
//
// 보안:
// - about:blank 는 same-origin (CatchUp) 이라 noopener 없이도 외부 코드 위협 0.
// - location.href 로 cross-origin (channel.io presigned) 으로 navigate 한 순간 Same-Origin Policy
//   가 window.opener 접근을 자동 차단 → reverse tabnabbing 자연 해소.
// - 응답 url 은 isSafeUrl 로 scheme 화이트리스트 검증 — javascript:/data: 등 차단.
//
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
import { isSafeUrl } from '@/shared/utils/isSafeUrl';

interface FileRowProps {
  file: OriginalFile;
  connector: SourceTypeApi;
  documentId: string;
}

// 빈 탭이 정상적으로 열렸으면 location 갱신. popup blocker 가 빈 탭마저 막은 경우(null) 안내 toast.
// (onSuccess 안에서 anchor.click() fallback 시도는 비동기 컨텍스트라 또 차단되므로 안 함.)
function navigateNewTab(win: Window | null, url: string): boolean {
  if (!win) return false;
  win.location.href = url;
  return true;
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
    // 클릭 동기 시점 — popup blocker 통과. noopener 없이 Window 참조 받음 (cross-origin navigate 후 자연 단절).
    const win = window.open('about:blank', '_blank');

    mutate(
      { connector, document_id: documentId, file_key: fileKey },
      {
        onSuccess: (res) => {
          // url 은 타입상 non-optional string 이지만 빈 문자열 방어 + scheme 화이트리스트 검증.
          const url = res.data.url;
          if (!url || !isSafeUrl(url)) {
            win?.close();
            toast.error('파일을 불러올 수 없습니다');
            return;
          }
          if (!navigateNewTab(win, url)) {
            // 빈 탭마저 차단된 경우 (popup blocker) — 사용자에게 안내.
            toast.error('팝업이 차단되어 파일을 열 수 없어요. 브라우저에서 팝업을 허용해주세요.');
          }
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
      className={`${baseClass} cursor-pointer ${isPending ? 'opacity-50' : ''}`.trim()}
    >
      {inner}
    </button>
  );
}
