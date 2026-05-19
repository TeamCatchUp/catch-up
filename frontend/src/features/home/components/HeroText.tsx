'use client';

// 홈/search 페이지 hero 영역의 텍스트.
// - ai 모드: 기본/포커스 두 줄 (포커스 시 다른 텍스트로 fade)
// - docs 모드: 단일 텍스트

import { Badge } from '@/shared/components/ui/badge';

import type { HomeMode } from './ModePicker';

interface HeroTextProps {
  mode: HomeMode;
  isFocused: boolean;
}

export default function HeroText({ mode, isFocused }: HeroTextProps) {
  if (mode === 'docs') {
    return (
      <div className="flex flex-col items-center gap-3 text-center [grid-area:1/1]">
        <div className="flex items-center gap-3">
          <Badge variant="default" size="sm" className="rounded-md2 text-body-xsmall py-0.5">
            New
          </Badge>
          <h1 className="text-heading-xlarge text-content-normal">어떤 정보를 찾고 계세요?</h1>
        </div>
        <p className="text-heading-medium text-content-alternative">
          {'"지난주 결제 롤백" 처럼 짧은 한 문장으로 적어주시면 빠르게 찾아드려요.'}
        </p>
      </div>
    );
  }

  return (
    <>
      <div
        className={`flex flex-col items-center gap-3 transition-opacity duration-300 [grid-area:1/1] ${
          isFocused ? 'pointer-events-none opacity-0' : 'opacity-100'
        }`}
      >
        <h1 className="text-heading-xlarge text-content-normal">동료에게 말하듯이 질문해 주세요</h1>
        <p className="text-heading-medium text-content-alternative">
          어렵게 적지 않아도 괜찮아요. 동료한테 말 걸듯 적으면 더 잘 대답할 수 있어요.
        </p>
      </div>
      <div
        className={`flex flex-col items-center text-center transition-opacity duration-300 [grid-area:1/1] ${
          isFocused ? 'opacity-100' : 'pointer-events-none opacity-0'
        }`}
      >
        <h1 className="text-heading-xlarge text-content-normal">
          사내 AI 탐색으로
          <br />
          <span className="text-content-primary">필요한 업무 자료를 </span>
          바로 찾아보세요
        </h1>
      </div>
    </>
  );
}
