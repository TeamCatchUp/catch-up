'use client';

/**
 * 답변 생성 과정 상단 topic 헤더.
 *
 * Figma: 12861-54617 / 12861-54618 (Standard 프레임 헤더 영역)
 * - padding: pt-3 (12px), pb-1 (4px), px-6 (24px)
 * - font: heading-medium (Pretendard SemiBold 17px / line-height 1.45)
 * - color: content-normal (#33363d)
 *
 * `topic`은 supervisor `content.query_topic`이 도착하기 전까지 null이며
 * 그 시점에는 RagAnswerSkeleton 자체가 마운트되지 않으므로 도착이 보장된다.
 */

interface TopicHeaderProps {
  topic: string | null;
}

export default function TopicHeader({ topic }: TopicHeaderProps) {
  if (!topic) return null;

  return (
    <div className="flex items-center gap-2 pt-3 pr-6 pb-1 pl-6">
      <h2 className="text-heading-medium text-content-normal min-w-0 flex-1 leading-snug">
        {topic}
      </h2>
    </div>
  );
}
