'use client';

// button 콘텐츠 — buttons[] 를 공통 Button(text 스타일)으로 렌더.
// 과거 대화 기록이므로 url 있는 버튼만 새 탭 링크, 나머지는 비활성 표시.

import type { OriginalButton, OriginalButtonPayload } from '@/features/hybrid-search/types/originalApi';
import { Button } from '@/shared/components/ui/button';
import { isSafeUrl } from '@/shared/utils/isSafeUrl';

interface ButtonContentProps {
  content: OriginalButtonPayload;
}

function OriginalButtonItem({ button }: { button: OriginalButton }) {
  const label = button.text?.trim() ? button.text : '버튼';
  const isLink = isSafeUrl(button.url);

  if (isLink) {
    return (
      <Button asChild variant="text-primary-blue" size="md">
        <a href={button.url} target="_blank" rel="noopener noreferrer">
          {label}
        </a>
      </Button>
    );
  }

  return (
    <Button type="button" variant="text-primary-blue" size="md" disabled>
      {label}
    </Button>
  );
}

export default function ButtonContent({ content }: ButtonContentProps) {
  return (
    <div className="flex flex-wrap gap-1">
      {content.buttons.map((button, index) => (
        <OriginalButtonItem key={`${button.text ?? 'button'}-${index}`} button={button} />
      ))}
    </div>
  );
}
