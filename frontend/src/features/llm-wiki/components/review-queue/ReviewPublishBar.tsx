import { Button } from '@/shared/components/ui/button';

interface ReviewPublishBarProps {
  /** [BE] can_review. false면 바 자체를 내지 않는다 — 단일 액션이라 버튼만 빼면 빈 띠가 남는다 */
  canReview?: boolean;
  onPublish: () => void;
}

/** 검토 큐 상세 하단의 고정 바 — "최종 내보내기" 단일 액션. */
export default function ReviewPublishBar({ canReview = true, onPublish }: ReviewPublishBarProps) {
  if (!canReview) return null;

  return (
    <div className="border-line-normal-neutral flex shrink-0 items-center justify-end border-t px-8 py-3">
      {/* 시안 높이 40은 Box lg 패딩 파생값(≈37)과 달라 고정한다 */}
      <Button variant="box-solid-primary" size="lg" className="h-10" onClick={onPublish}>
        최종 내보내기
      </Button>
    </div>
  );
}
