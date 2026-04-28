'use client';

import { useId, useState } from 'react';

import IconVisibilityOff from '@/public/icons/icon/visibility_off.svg';
import { cn } from '@/shared/utils/cn';

import type { ChannelTalkFieldState } from '../../../types/channelTalkModel';

interface ChannelTalkTextFieldProps {
  value: string;
  placeholder: string;
  state?: ChannelTalkFieldState;
  /** 비밀값 입력 — eye-off 토글 버튼 노출 (기본은 평문 표시, 클릭 시 마스킹) */
  maskable?: boolean;
  /** 초기 마스킹 여부 (maskable=true일 때만 적용, 기본 false = 평문 표시) */
  defaultMasked?: boolean;
  /** lock 상태 — readOnly + 회색 배경 (`bg-fill-interaction-disable`). eye 토글은 여전히 동작 */
  disabled?: boolean;
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
  defaultMasked = false,
  disabled = false,
  onChange,
  readOnly,
  id,
  'aria-label': ariaLabel,
}: ChannelTalkTextFieldProps) {
  const reactId = useId();
  const inputId = id ?? reactId;
  const [masked, setMasked] = useState(defaultMasked);
  const showMaskToggle = maskable;

  return (
    <div
      className={cn(
        'flex h-11.5 max-h-45 min-h-11.5 w-full items-center gap-3 rounded-lg p-3',
        disabled ? 'bg-fill-interaction-disable border-edge-neutral border' : 'bg-fill-normal',
        !disabled && state === 'idle' && 'border-edge-neutral border',
        !disabled && state === 'error' && 'border-status-destructive border-[1.5px]',
        !disabled && state === 'focus' && 'border-edge-primary border-[1.5px]',
      )}
    >
      <input
        id={inputId}
        type={maskable && masked ? 'password' : 'text'}
        value={value}
        onChange={(e) => onChange?.(e.target.value)}
        placeholder={placeholder}
        readOnly={readOnly || disabled}
        aria-label={ariaLabel}
        className={cn(
          'text-body-small placeholder:text-content-assistive min-w-0 flex-1 truncate bg-transparent outline-none',
          disabled ? 'text-content-assistive cursor-not-allowed' : 'text-content-normal',
        )}
      />
      {showMaskToggle && (
        <button
          type="button"
          aria-label={masked ? '값 표시' : '값 숨기기'}
          onClick={() => setMasked((prev) => !prev)}
          className="text-icon-alternative hover:text-icon-normal flex size-4.5 shrink-0 cursor-pointer items-center justify-center transition-colors"
        >
          <IconVisibilityOff className="size-4.5" />
        </button>
      )}
    </div>
  );
}
