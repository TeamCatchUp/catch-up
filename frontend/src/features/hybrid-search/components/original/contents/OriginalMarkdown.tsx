'use client';

// 원문 메시지 본문의 인라인 마크다운(굵게/기울임/링크) 렌더.
// 채팅 답변용 .markdown-body(16px 문서 스타일)와 달리 원문 패널은 body-small 컴팩트 스타일.

import type { Components } from 'react-markdown';
import ReactMarkdown from 'react-markdown';
import remarkBreaks from 'remark-breaks';
import remarkGfm from 'remark-gfm';

import { formatMarkdownString } from '@/shared/utils/formatMarkdownString';
import { isSafeUrl } from '@/shared/utils/isSafeUrl';

interface OriginalMarkdownProps {
  text: string;
}

const components: Components = {
  p: ({ children }) => <p className="break-words">{children}</p>,
  strong: ({ children }) => <strong className="font-bold">{children}</strong>,
  ul: ({ children }) => <ul className="flex list-disc flex-col gap-2 pl-5">{children}</ul>,
  ol: ({ children }) => <ol className="flex list-decimal flex-col gap-2 pl-5">{children}</ol>,
  li: ({ children }) => <li className="break-words">{children}</li>,
  a: ({ href, children }) => {
    if (typeof href !== 'string' || !isSafeUrl(href)) {
      return <>{children}</>;
    }
    return (
      <a
        href={href}
        target="_blank"
        rel="noopener noreferrer"
        className="text-content-primary underline"
      >
        {children}
      </a>
    );
  },
};

export default function OriginalMarkdown({ text }: OriginalMarkdownProps) {
  return (
    <div className="text-body-small text-content-normal flex flex-col gap-2">
      <ReactMarkdown remarkPlugins={[remarkGfm, remarkBreaks]} components={components}>
        {formatMarkdownString(text)}
      </ReactMarkdown>
    </div>
  );
}
