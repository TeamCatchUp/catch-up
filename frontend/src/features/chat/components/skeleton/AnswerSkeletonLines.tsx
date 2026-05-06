'use client';

/**
 * 답변 token 도착 전 답변 본문 영역에 노출되는 placeholder lines.
 *
 * Figma: 8:1376 (PUTbzuFPWFtDwuVGx9e3cn / 8-1369 frame)
 * - 5개 라인, height 16px, rounded-lg(8px), bg #f7f7f8 (fill-strong)
 * - 너비 점차 줄어듦: 405 / 343 / 298 / 243 / 178 (px)
 * - gap-3 (12px) between lines
 * - shimmer 효과 (animate-shimmer-line — animation.css)
 *
 * 마운트 조건: `RagAnswerSkeleton` 안에서 PipelineTypeBanner 아래.
 *  - showSkeleton 조건과 동일 — 답변 token 첫 도착 시 unmount.
 */

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
