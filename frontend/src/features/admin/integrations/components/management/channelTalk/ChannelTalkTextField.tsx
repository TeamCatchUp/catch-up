'use client';

import { useId, useState } from 'react';

import IconVisibility from '@/public/icons/icon/visibility.svg';
import IconVisibilityOff from '@/public/icons/icon/visibility_off.svg';
import { cn } from '@/shared/utils/cn';

/**
 * ChannelTalkTextField 시각 변형 (Figma node `12004:101461` 5상태 머신 매핑).
 * - `idle`: 1px `border-edge-neutral` (#eaebec) — 입력 전 / 입력 완료 / 테스트 성공
 * - `error`: 1.5px `border-status-destructive` (#ff4242) — Error_미입력
 * - `focus`: 1.5px `border-edge-primary` (#69a5ff) — Key 수정 → 재시도 유도
 */
type ChannelTalkTextFieldState = 'idle' | 'error' | 'focus';

interface ChannelTalkTextFieldProps {
  value: string;
  placeholder: string;
  state?: ChannelTalkTextFieldState;
  /** 비밀값 입력 — value가 있을 때 eye 토글 버튼 노출 */
  maskable?: boolean;
  /** 초기 마스킹 여부 (maskable=true일 때만 적용) */
  defaultMasked?: boolean;
  onChange?: (next: string) => void;
  readOnly?: boolean;
  id?: string;
  'aria-label'?: string;
}

/** 채널톡 Access Key/Secret/Webhook Token 입력용 텍스트필드 (5상태 + 마스킹 토글) */
export default function ChannelTalkTextField({
  value,
  placeholder,
  state = 'idle',
  maskable = false,
  defaultMasked = true,
  onChange,
  readOnly,
  id,
  'aria-label': ariaLabel,
}: ChannelTalkTextFieldProps) {
  const reactId = useId();
  const inputId = id ?? reactId;
  const [masked, setMasked] = useState(defaultMasked);
  const showMaskToggle = maskable && value.length > 0;

  return (
    <div
      className={cn(
        'bg-fill-normal flex h-11.5 max-h-45 min-h-11.5 w-full items-center gap-3 rounded-lg p-3',
        state === 'idle' && 'border-edge-neutral border',
        state === 'error' && 'border-status-destructive border-[1.5px]',
        state === 'focus' && 'border-edge-primary border-[1.5px]',
      )}
    >
      <input
        id={inputId}
        type={maskable && masked ? 'password' : 'text'}
        value={value}
        onChange={(e) => onChange?.(e.target.value)}
        placeholder={placeholder}
        readOnly={readOnly}
        aria-label={ariaLabel}
        className="text-body-small text-content-normal placeholder:text-content-assistive min-w-0 flex-1 truncate bg-transparent outline-none"
      />
      {showMaskToggle && (
        <button
          type="button"
          aria-label={masked ? '값 표시' : '값 숨기기'}
          onClick={() => setMasked((prev) => !prev)}
          className="text-icon-alternative hover:text-icon-normal flex size-4.5 shrink-0 cursor-pointer items-center justify-center transition-colors"
        >
          {masked ? <IconVisibilityOff className="size-4.5" /> : <IconVisibility className="size-4.5" />}
        </button>
      )}
    </div>
  );
}
