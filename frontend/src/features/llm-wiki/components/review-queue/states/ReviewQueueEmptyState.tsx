import IconEmptyDocument from '@/public/icons/icon/empty_document.svg';

/** 검토할 변경안이 없을 때 상세 자리에 들어가는 안내. 좌측 목록 머리글과 필터는 그대로 남는다. */
export default function ReviewQueueEmptyState() {
  return (
    <div className="flex h-full w-full flex-col items-center justify-center gap-5">
      <IconEmptyDocument aria-hidden className="h-13.75 w-16 shrink-0" />
      <p className="text-body-xsmall text-text-normal-assistive text-center">요청된 변경사항이 없어요</p>
    </div>
  );
}
