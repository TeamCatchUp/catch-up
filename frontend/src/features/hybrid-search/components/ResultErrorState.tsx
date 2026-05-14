'use client';

// Figma 명시 없음 — Empty/Loading와 동일한 py-50 + gap-2 패턴으로 시각 통일.

interface ResultErrorStateProps {
  onRetry: () => void;
}

export default function ResultErrorState({ onRetry }: ResultErrorStateProps) {
  return (
    <div className="flex flex-col items-center gap-2 py-50">
      <p className="text-body-small text-content-alternative">
        검색 중 오류가 발생했어요. 다시 시도해주세요.
      </p>
      <button
        type="button"
        onClick={onRetry}
        className="text-body-small text-content-primary hover:bg-fill-primary-interaction-hover-assistive cursor-pointer rounded-full px-3 py-1.5 font-medium transition-colors"
      >
        다시 시도
      </button>
    </div>
  );
}
