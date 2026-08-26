'use client';

// 홈 컴포저 위의 인사/안내 문구. 두 모드가 같은 구조에 문구만 다르다.

import type { HomeMode } from './ComposerModeToggle';

interface HeroTextProps {
  mode: HomeMode;
  userName?: string;
}

const DOCS_HEADING = '어떤 정보를 찾고 계세요?';
const DOCS_SUBHEADING = '"지난주 결제 롤백" 처럼 짧은 한 문장으로 적어주시면 빠르게 찾아드려요';
const AI_SUBHEADING = '무엇을 도와드릴까요? 필요한 업무정보를 찾아보세요';

export default function HeroText({ mode, userName = '' }: HeroTextProps) {
  const heading = mode === 'docs' ? DOCS_HEADING : userName ? `반갑습니다, ${userName}님!` : '반갑습니다!';
  const subheading = mode === 'docs' ? DOCS_SUBHEADING : AI_SUBHEADING;

  return (
    <div className="flex flex-col items-center gap-3 text-center">
      <h1 className="text-display-large text-text-normal-normal">{heading}</h1>
      <p className="text-heading-large text-text-normal-alternative">{subheading}</p>
    </div>
  );
}
