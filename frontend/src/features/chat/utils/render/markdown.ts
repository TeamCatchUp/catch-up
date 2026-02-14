/**
 * 마크다운 문자열을 ReactMarkdown에서 올바르게 렌더링할 수 있도록 포맷팅
 *
 * - 줄바꿈 문자 통일 (\r\n, \r -> \n)
 * - 이스케이프된 줄바꿈 처리 (\\n -> \n)
 * - 인라인 코드 주변 공백 보정
 * - 블록 문법 앞 빈 줄 보정 (헤딩, 리스트, 코드펜스 등)
 */
export const formatMarkdownString = (text: string): string => {
  if (!text) return '';

  // \r\n, \r을 \n으로 통일
  let normalized = text.replace(/\r\n/g, '\n').replace(/\r/g, '\n').replace(/\\n/g, '\n');

  // strong 안의 백틱 코드 앞/뒤에 바로 글자가 오는 경우 띄어쓰기 추가
  // 예: **`code`**글자 -> **`code`** 글자
  normalized = normalized.replace(/(\*\*`[^`]+`\*\*)([^\s*])/g, '$1 $2');

  // 블록 문법 시작(헤딩/리스트/체크박스/코드펜스/인용/테이블) 앞에 빈 줄 보정
  const withSpacing = normalized.replace(
    /([^\n])\n(?=(#{1,6}\s|(\d+)\.\s|[-*+]\s|-\s\[[xX\s]\]\s|```|>\s|\|))/g,
    '$1\n\n',
  );

  return withSpacing.trimEnd();
};
