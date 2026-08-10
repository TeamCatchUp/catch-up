import type { ComponentType, SVGProps } from 'react';

/**
 * 에디터 전용 임시 아이콘 세트 (스펙 §12 아이콘 방침).
 *
 * public/icons/icon/ 공용 자산에 없는 글리프만 에디터 폴더 안에 스코프해 둔다 —
 * 디자이너 자산이 도착하면 이 파일 하나만 교체한다. design-request의 아이콘 요청은 유지 중.
 * 제목·번호 목록은 노션과 같은 문자 글리프(H1·H2·H3·1.)를 SVG <text>로 감쌌다.
 *
 * **여기에 넣기 전에 public/icons/icon/를 먼저 뒤진다.** 8/10 감사에서 IconPlus가
 * `add.svg`와 중복이라 제거됐다 — 이 파일의 존재 이유는 "임시 대체"이지 "새 아이콘 서랍"이 아니다.
 */

type Icon = ComponentType<SVGProps<SVGSVGElement>>;

function textGlyph(label: string, fontSize = 9): Icon {
  function TextGlyphIcon(props: SVGProps<SVGSVGElement>) {
    return (
      <svg viewBox="0 0 20 20" aria-hidden {...props}>
        <text
          x="10"
          y="14"
          textAnchor="middle"
          fontSize={fontSize}
          fontWeight={700}
          fill="currentColor"
          fontFamily="inherit"
        >
          {label}
        </text>
      </svg>
    );
  }
  TextGlyphIcon.displayName = `TextGlyphIcon(${label})`;
  return TextGlyphIcon;
}

export const IconHeading1 = textGlyph('H1');
export const IconHeading2 = textGlyph('H2');
export const IconHeading3 = textGlyph('H3');
export const IconOrderedList = textGlyph('1.');
export const IconCode = textGlyph('</>', 7);

export function IconQuote(props: SVGProps<SVGSVGElement>) {
  return (
    <svg viewBox="0 0 20 20" aria-hidden fill="none" stroke="currentColor" strokeWidth="1.5" {...props}>
      <line x1="5" y1="4" x2="5" y2="16" strokeWidth="2" />
      <line x1="9" y1="6" x2="16" y2="6" />
      <line x1="9" y1="10" x2="16" y2="10" />
      <line x1="9" y1="14" x2="14" y2="14" />
    </svg>
  );
}

export function IconTable(props: SVGProps<SVGSVGElement>) {
  return (
    <svg viewBox="0 0 20 20" aria-hidden fill="none" stroke="currentColor" strokeWidth="1.5" {...props}>
      <rect x="3" y="4" width="14" height="12" rx="1" />
      <line x1="3" y1="8.5" x2="17" y2="8.5" />
      <line x1="10" y1="4" x2="10" y2="16" />
    </svg>
  );
}

export function IconCheckbox(props: SVGProps<SVGSVGElement>) {
  return (
    <svg viewBox="0 0 20 20" aria-hidden fill="none" stroke="currentColor" strokeWidth="1.5" {...props}>
      <rect x="3.5" y="3.5" width="13" height="13" rx="2.5" />
      <path d="M7 10.2 9.2 12.4 13.4 7.6" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

export function IconCallout(props: SVGProps<SVGSVGElement>) {
  return (
    <svg viewBox="0 0 20 20" aria-hidden fill="none" stroke="currentColor" strokeWidth="1.5" {...props}>
      <rect x="3" y="4.5" width="14" height="11" rx="2" />
      <line x1="6.5" y1="4.5" x2="6.5" y2="15.5" />
    </svg>
  );
}

export function IconParagraph(props: SVGProps<SVGSVGElement>) {
  return (
    <svg viewBox="0 0 20 20" aria-hidden fill="none" stroke="currentColor" strokeWidth="1.5" {...props}>
      <line x1="4" y1="5" x2="16" y2="5" />
      <line x1="4" y1="10" x2="16" y2="10" />
      <line x1="4" y1="15" x2="11" y2="15" />
    </svg>
  );
}
