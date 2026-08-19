import IconEmptyDocument from '@/public/icons/icon/empty_document.svg';

interface DocumentTableEmptyStateProps {
  /** 행 대상이 문서가 아닐 때만 바꾼다 — 일러스트·레이아웃은 문구와 무관하게 동일하다 */
  message?: string;
}

/** 표에 보여줄 행이 없을 때 행 자리에 들어가는 안내. 표 헤더는 그대로 남는다. */
export default function DocumentTableEmptyState({ message = '문서가 없어요' }: DocumentTableEmptyStateProps) {
  return (
    <div className="flex w-full flex-col items-center gap-5 py-45">
      <IconEmptyDocument aria-hidden className="h-13.75 w-16 shrink-0" />
      <p className="text-body-xsmall text-text-normal-assistive text-center">{message}</p>
    </div>
  );
}
