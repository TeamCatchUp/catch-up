'use client';

// 원문 메시지의 코드 블럭. block_type:'code' 에서 매핑된다.
// 하이라이터 없음 — 회색 surface + 긴 줄 가로 스크롤, 최대 높이 제한.
// max-h/overflow 는 <pre> 에 둠 — 부모에 두면 <pre> 하단 가로 스크롤바가 잘림.

interface CodeBlockProps {
  code: string;
}

export default function CodeBlock({ code }: CodeBlockProps) {
  return (
    <div className="bg-fill-strong border-edge-neutral w-full overflow-hidden rounded-lg border">
      <pre className="custom-scrollbar m-0 max-h-62.5 overflow-auto px-4 py-3 font-[inherit]">
        <code className="text-body-small text-content-neutral font-[inherit] whitespace-pre">
          {code}
        </code>
      </pre>
    </div>
  );
}
