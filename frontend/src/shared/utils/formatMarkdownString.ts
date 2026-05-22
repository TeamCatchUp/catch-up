// 마크다운 문자열을 ReactMarkdown 렌더링에 맞게 정규화.
// - 줄바꿈 통일(\r\n, \r → \n), 이스케이프 줄바꿈(\\n → \n)
// - strong 내부 인라인 코드 뒤 공백 보정
// - 블록 문법(헤딩/리스트/체크박스/코드펜스/인용/테이블) 앞 빈 줄 보정

export const formatMarkdownString = (text: string): string => {
  if (!text) return '';

  // \r\n, \r을 \n으로 통일
  let normalized = text.replace(/\r\n/g, '\n').replace(/\r/g, '\n').replace(/\\n/g, '\n');

  // **`code`**글자 -> **`code`** 글자
  normalized = normalized.replace(/(\*\*`[^`]+`\*\*)([^\s*])/g, '$1 $2');

  // 블록 문법 시작 앞에 빈 줄 보정
  const withSpacing = normalized.replace(
    /([^\n])\n(?=(#{1,6}\s|(\d+)\.\s|[-*+]\s|-\s\[[xX\s]\]\s|```|>\s))/g,
    '$1\n\n',
  );

  // 테이블 시작 전 빈 줄 보정 (이전 행이 |로 시작하지 않는 경우만)
  const withTableSpacing = withSpacing.replace(/^([^|\n].*)\n(\|)/gm, '$1\n\n$2');

  return withTableSpacing.trimEnd();
};
