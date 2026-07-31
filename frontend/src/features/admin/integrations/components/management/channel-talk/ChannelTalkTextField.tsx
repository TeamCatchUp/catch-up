'use client';

import { useId, useState } from 'react';

import IconVisibility from '@/public/icons/icon/visibility.svg';
import IconVisibilityOff from '@/public/icons/icon/visibility_off.svg';
import { cn } from '@/shared/utils/cn';

interface ChannelTalkTextFieldProps {
  value: string;
  placeholder: string;
  // error → 1.5px destructive border, idle → 1px neutral
  state?: 'idle' | 'error';
  // eye-off 토글 노출 (기본 평문, 클릭 시 마스킹)
  maskable?: boolean;
  // maskable=true일 때만 초기 마스킹 적용
  defaultMasked?: boolean;
  // readOnly + 회색 배경. eye 토글은 동작 유지
  disabled?: boolean;
  onChange?: (next: string) => void;
  readOnly?: boolean;
  id?: string;
  'aria-label'?: string;
}

// 채널톡 Access Key/Secret/Webhook Token 입력 (idle/error + 마스킹 토글)
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
  // 사용자가 eye 토글로 직접 설정한 마스킹 의도
  const [userMasked, setUserMasked] = useState(defaultMasked);
  // disabled(tested lock) 진입 시 사용자 의도와 무관하게 강제 마스킹
  const masked = disabled ? true : userMasked;
  const showMaskToggle = maskable;
  // type=password 사용 — value에 '*' 박으면 cursor jump 발생
  const inputType = maskable && masked ? 'password' : 'text';

  return (
    <div
      className={cn(
        // ring으로 테두리 — 상태 전환 시 layout shift 0
        'flex h-11.5 max-h-45 min-h-11.5 w-full items-center gap-3 rounded-lg p-3 ring-[1.5px] ring-inset',
        disabled ? 'bg-fill-normal-interaction-disable ring-line-normal-neutral' : 'bg-fill-normal-normal',
        !disabled && state === 'idle' && 'ring-line-normal-neutral focus-within:ring-line-primary-normal',
        !disabled && state === 'error' && 'ring-status-destructive',
      )}
    >
      <input
        id={inputId}
        type={inputType}
        value={value}
        onChange={(e) => onChange?.(e.target.value)}
        placeholder={placeholder}
        readOnly={readOnly || disabled}
        aria-label={ariaLabel}
        className={cn(
          'text-body-small placeholder:text-text-normal-assistive min-w-0 flex-1 truncate bg-transparent outline-none',
          disabled ? 'text-text-normal-assistive cursor-not-allowed' : 'text-text-normal-normal',
        )}
      />
      {showMaskToggle && (
        <button
          type="button"
          data-mask-toggle="true"
          aria-label={masked ? '값 표시' : '값 숨기기'}
          onClick={() => setUserMasked((prev) => !prev)}
          className="text-icon-normal-alternative hover:text-icon-normal-normal flex size-4.5 shrink-0 cursor-pointer items-center justify-center transition-colors"
        >
          {masked ? <IconVisibilityOff className="size-4.5" /> : <IconVisibility className="size-4.5" />}
        </button>
      )}
    </div>
  );
}
