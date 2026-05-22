// text 콘텐츠 — payload.text 를 줄바꿈 보존 평문으로 렌더.

import type { OriginalTextPayload } from '@/features/hybrid-search/types/originalApi';

interface TextContentProps {
  content: OriginalTextPayload;
}

export default function TextContent({ content }: TextContentProps) {
  return (
    <p className="text-body-small text-content-neutral break-words whitespace-pre-wrap">
      {content.text}
    </p>
  );
}
