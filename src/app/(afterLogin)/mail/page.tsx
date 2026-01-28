export default function Mail() {
  return <div className="flex items-center justify-center">수신함 페이지</div>;
}

// 'use client';

// import clsx from 'clsx';
// import { useState, useRef, useEffect, useCallback } from 'react';
// import ReactMarkdown from 'react-markdown';
// import remarkGfm from 'remark-gfm';

// const mockMD = `
// # h1 제목

// - 가나다abc \`단독 인라인코드\` \`단어+인라인코드\`랑
// - **\`strong 인라인코드\`** \`strong 단어+인라인코드\`랑
// - **\`여기서안되네\`**

// > 인용문1
// > blockquoteblockquoteblockquoteblockquoteblockquoteblockquoteblockquoteblockquoteblockquoteblockquoteblockquoteblockquoteblockquoteblockquoteblockquoteblockqublockquoteblockquoteblockquoteblockquoteblockquoteblockquoteblockquoteblockquoteblockquoteblockquoteblockquoteblockquoteblockquoteblockquoteblockquoteblockqublockquoteblockquoteblockquoteblockquoteblockquoteblockquoteblockquoteblockquoteblockquoteblockquoteblockquoteblockquoteblockquoteblockquoteblockquoteblockquote

// ### h3 제목

// **strong** strong **strong**아
// - 링크: [naver](https://naver.com)
// - 링크에 \`inline\`도 섞기: [\`/api/chat/resume\` 문서](https://example.com/api-docs)

// ## 리스트 (ul / ol / 중첩)

// - ul 1번
// - ul 2번
//   - ul 2-1 (중첩)
//   - ul 2-2 (중첩)
//     - ul 2-2-1 (더 중첩)
// - ul 3번

// 1. ol 1번
// 2. ol 2번
//    1. ol 2-1 (중첩)
//    2. ol 2-2 (중첩)
// 3. ol 3번

// ## 코드블럭 (pre > code)

// \`\`\`ts
// type RagNotification = {
//   target: 'CHAT';
//   type: 'RAG_IN_PROGRESS' | 'RAG_INTERRUPT' | 'RAG_DONE';
//   message: string | null;
//   data: {
//     sessionId: string;
//     type: 'status' | 'interrupt' | 'result' | 'interrupt' | 'result'  | 'interrupt' | 'result' | 'interrupt' | 'result' | 'interrupt' | 'result' | 'interrupt' | 'result';
//     node: string;
//     payload?: unknown;
//     response?: {
//       answer: string;
//       sources?: Array<{ sourceType: number; title: string }>;
//     };
//   };
// };

// function demoInlineVsBlock() {
//   const endpoint = '/api/notification/subscribe';
//   console.log('SSE endpoint:', endpoint);
// }
// \`\`\`

// \`\`\`bash
// # curl example
// curl -N -H "Accept:text/event-stream" "https://example.com/api/notification/subscribe"
// \`\`\`

// ## H2: 테이블 (table)

// | 항목 | 설명 | 예시 |
// |---|---|---|
// | sessionId | 세션 식별자 | \`746a8ca1-19d6-4d35-b80e-401f97ecbda8\` |
// | node | RAG 단계 | \`router\`, \`retrieve\`, \`rerank\`, \`generate\` |
// | type | 이벤트 타입 | \`RAG_IN_PROGRESS\`, \`RAG_DONE\` |

// ## H2: 이미지 (img)

// ![테스트 이미지](https://picsum.photos/800/450)

// ## H2: 마무리

// 인라인 코드 \`final_check=true\` 와 **굵게 표시**! **굵게 표시**

// 줄

// 바

// 꿈
// `;

// export default function Mail() {
//   const formatMarkdownString = (text: string) => {
//     if (!text) return '';

//     const normalized = text.replace(/\r\n/g, '\n').replace(/\r/g, '\n').replace(/\\n/g, '\n');

//     // 블록 문법 시작(헤딩/리스트/체크박스/코드펜스/인용/테이블) 앞에 빈 줄 보정
//     const withSpacing = normalized.replace(
//       /([^\n])\n(?=(#{1,6}\s|(\d+)\.\s|[-*+]\s|-\s\[[xX\s]\]\s|```|>\s|\|))/g,
//       '$1\n\n',
//     );

//     return withSpacing.trimEnd();
//   };

//   return (
//     <div className="markdown-body max-w-192.75 p-10 break-words [&_pre]:overflow-x-auto [&_pre]:break-words [&>ol]:list-decimal [&>ul]:list-disc">
//       <ReactMarkdown
//         remarkPlugins={[remarkGfm]}
//         components={{
//           table: ({ children, ...props }) => (
//             <div className="table-wrapper">
//               <table {...props}>{children}</table>
//             </div>
//           ),
//         }}
//       >
//         {formatMarkdownString(mockMD)}
//       </ReactMarkdown>
//     </div>
//   );
// }
