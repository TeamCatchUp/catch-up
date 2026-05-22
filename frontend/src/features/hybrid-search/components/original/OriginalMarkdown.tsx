'use client';

// 원문 메시지 본문의 인라인 마크다운(굵게/기울임/링크) 렌더.

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
  a: ({ href, children }) => {
    if (typeof href !== 'string' || !isSafeUrl(href)) {
      return <>{children}</>;
    }
    return (
      <a href={href} target="_blank" rel="noopener noreferrer">
        {children}
      </a>
    );
  },
};

export default function OriginalMarkdown({ text }: OriginalMarkdownProps) {
  return (
    <div className="markdown-body">
      <ReactMarkdown remarkPlugins={[remarkGfm, remarkBreaks]} components={components}>
        {formatMarkdownString(text)}
      </ReactMarkdown>
    </div>
  );
}
