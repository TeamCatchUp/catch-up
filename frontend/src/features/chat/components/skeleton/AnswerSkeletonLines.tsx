'use client';

const SKELETON_LINE_WIDTHS = [405, 343, 298, 243, 178];
const STAGGER_MS = 260;

export default function AnswerSkeletonLines() {
  return (
    <div className="animate-breath flex w-full flex-col gap-3">
      {SKELETON_LINE_WIDTHS.map((w, i) => (
        <div
          key={i}
          aria-hidden
          className="animate-line-drop bg-fill-strong h-4 max-w-full rounded-lg"
          style={{
            width: `${w}px`,
            animationDelay: `${i * STAGGER_MS}ms`,
          }}
        />
      ))}
    </div>
  );
}
