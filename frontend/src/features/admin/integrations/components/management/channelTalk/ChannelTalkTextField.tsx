'use client';

import { useId, useState } from 'react';

import IconVisibility from '@/public/icons/icon/visibility.svg';
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
  /** 사용자가 eye 토글로 직접 변경한 마스킹 의도 (defaultMasked 초기값) */
  const [userMasked, setUserMasked] = useState(defaultMasked);
  /**
   * 실제 마스킹 여부 — disabled(tested lock) 진입 시 사용자 의도와 무관하게 강제 마스킹.
   * 렌더 시점 파생값이라 useEffect + setState 패턴이 불필요.
   */
  const masked = disabled ? true : userMasked;
  const showMaskToggle = maskable;
  /**
   * 마스킹은 input type=password로 처리 (브라우저 native).
   * 직접 '*'를 value에 채워넣으면 입력 도중 토글 시 readOnly 또는 cursor jump 발생 → 입력 깨짐.
   * type=password로 두면 raw value는 그대로, 시각만 dot으로 가려져서 입력 도중에도 자유롭게 토글 가능.
   */
  const inputType = maskable && masked ? 'password' : 'text';

  return (
    <div
      className={cn(
        'flex h-11.5 max-h-45 min-h-11.5 w-full items-center gap-3 rounded-lg p-3',
        disabled ? 'bg-fill-interaction-disable border-edge-neutral border' : 'bg-fill-normal',
        // 외부에서 'focus'를 강제 지정한 경우(검증 권유 등)는 그대로 우선.
        // idle은 native focus-within으로 사용자 입력 시점 자동 강조.
        !disabled &&
          state === 'idle' &&
          'border-edge-neutral focus-within:border-edge-primary border focus-within:border-[1.5px]',
        !disabled && state === 'error' && 'border-status-destructive border-[1.5px]',
        !disabled && state === 'focus' && 'border-edge-primary border-[1.5px]',
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
          'text-body-small placeholder:text-content-assistive min-w-0 flex-1 truncate bg-transparent outline-none',
          disabled ? 'text-content-assistive cursor-not-allowed' : 'text-content-normal',
        )}
      />
      {showMaskToggle && (
        <button
          type="button"
          data-mask-toggle="true"
          aria-label={masked ? '값 표시' : '값 숨기기'}
          onClick={() => setUserMasked((prev) => !prev)}
          className="text-icon-alternative hover:text-icon-normal flex size-4.5 shrink-0 cursor-pointer items-center justify-center transition-colors"
        >
          {masked ? <IconVisibilityOff className="size-4.5" /> : <IconVisibility className="size-4.5" />}
        </button>
      )}
    </div>
  );
}
