'use client';

const SKELETON_LINE_WIDTHS = [405, 343, 298, 243, 178];

export default function AnswerSkeletonLines() {
  return (
    <div className="flex w-full flex-col gap-3">
      {SKELETON_LINE_WIDTHS.map((w, i) => (
        <div
          key={i}
          aria-hidden
          className="animate-shimmer-line h-4 max-w-full rounded-lg"
          style={{ width: `${w}px` }}
        />
      ))}
    </div>
  );
}
