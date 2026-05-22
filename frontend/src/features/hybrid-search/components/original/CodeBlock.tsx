'use client';

// 원문 메시지의 코드 블럭. block_type:'code' 에서 매핑된다.
// 하이라이터 없음 — 회색 surface + 긴 줄 가로 스크롤.

interface CodeBlockProps {
  code: string;
  language?: string;
}

export default function CodeBlock({ code, language }: CodeBlockProps) {
  return (
    <div className="bg-fill-strong border-edge-neutral w-full overflow-hidden rounded-lg border">
      {language && (
        <span className="text-body-xsmall text-content-alternative border-edge-neutral block border-b px-3 py-1.5">
          {language}
        </span>
      )}
      <pre className="custom-scrollbar overflow-x-auto px-3 py-2.5">
        <code className="text-body-small text-content-neutral font-mono whitespace-pre">{code}</code>
      </pre>
    </div>
  );
}
