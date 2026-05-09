'use client';

import ChannelTalkTextField from './ChannelTalkTextField';

interface ChannelTalkFieldRowProps {
  label: string;
  value: string;
  placeholder: string;
  // error → 1.5px destructive border, idle → 1px neutral border
  state: 'idle' | 'error';
  // 입력 불가 + 회색 배경 + 자동 마스킹
  disabled?: boolean;
  onChange: (next: string) => void;
}

// 채널/도큐먼트 스페이스 공용 입력 행 (라벨 + 필수 dot + 마스킹 textfield)
export default function ChannelTalkFieldRow({
  label,
  value,
  placeholder,
  state,
  disabled,
  onChange,
}: ChannelTalkFieldRowProps) {
  return (
    <div className="flex min-w-0 flex-1 flex-col gap-1.5">
      <div className="flex items-center gap-1">
        <span className="text-body-small text-content-neutral">{label}</span>
        <span className="bg-status-destructive size-[5px] rounded-full" aria-label="필수 입력" />
      </div>
      <ChannelTalkTextField
        value={value}
        placeholder={placeholder}
        state={state}
        maskable
        disabled={disabled}
        defaultMasked={disabled}
        onChange={onChange}
      />
    </div>
  );
}
