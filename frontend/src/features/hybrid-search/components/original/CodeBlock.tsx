'use client';

// 원문 메시지의 코드 블럭. block_type:'code' 에서 매핑된다.
// 하이라이터 없음 — 회색 surface + 긴 줄 가로 스크롤, 최대 높이 제한.

interface CodeBlockProps {
  code: string;
  language?: string;
}

export default function CodeBlock({ code, language }: CodeBlockProps) {
  return (
    <div className="bg-fill-strong border-edge-neutral max-h-62.5 w-full overflow-hidden rounded-lg border">
      {language && (
        <span className="text-body-xsmall text-content-alternative border-edge-neutral block border-b px-4 py-1.5">
          {language}
        </span>
      )}
      <pre className="custom-scrollbar m-0 overflow-x-auto px-4 py-3 font-[inherit]">
        <code className="text-body-small text-content-neutral font-[inherit] whitespace-pre">
          {code}
        </code>
      </pre>
    </div>
  );
}
