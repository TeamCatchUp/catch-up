'use client';

/** 토큰 사용량 관리 > 나의 토큰 사용량 — 하루/월 최대 토큰 비용 제한 설정 (값 변경 시 저장 버튼 활성화, 저장 시 토스트 알림) */

import { useId, useState } from 'react';
import { toast } from 'sonner';

import { Button } from '@/shared/components/ui/button';
import { Input } from '@/shared/components/ui/input';

import { DEFAULT_DAILY_LIMIT, DEFAULT_MONTHLY_LIMIT } from '../../constants/tokenUsageConfig';

interface LimitRowProps {
  title: string;
  description: string;
  defaultValue: number;
  hasBorder: boolean;
}

function LimitRow({ title, description, defaultValue, hasBorder }: LimitRowProps) {
  const id = useId();
  const inputId = `${id}-input`;
  const descId = `${id}-desc`;

  const [value, setValue] = useState(String(defaultValue));
  const [savedValue, setSavedValue] = useState(String(defaultValue));

  const isDirty = value !== savedValue;

  const handleSave = () => {
    setSavedValue(value);
    toast('토큰 비용이 저장되었습니다.');
  };

  return (
    <div className={`flex items-center gap-5 py-3 ${hasBorder ? 'border-edge-neutral border-b' : ''}`}>
      {/* 설명 */}
      <div className="flex flex-1 flex-col gap-1.5">
        <label htmlFor={inputId} className="text-heading-small text-content-normal">
          {title}
        </label>
        <span id={descId} className="text-label-small text-content-alternative whitespace-pre-line">
          {description}
        </span>
      </div>

      {/* 입력 + 단위 + 저장 */}
      <div className="flex shrink-0 items-center gap-4">
        <div className="flex items-center gap-2.5">
          <Input
            id={inputId}
            inputSize="lg"
            className="w-72.5"
            value={value}
            placeholder={`${defaultValue}(기본값)`}
            aria-describedby={descId}
            onChange={(e) => setValue(e.target.value)}
          />
          <span className="text-body-small text-content-alternative" aria-hidden="true">
            $
          </span>
        </div>
        <Button variant="capsule-solid-primary" size="sm" className="w-16" disabled={!isDirty} onClick={handleSave}>
          {isDirty ? '저장' : '저장됨'}
        </Button>
      </div>
    </div>
  );
}

type TokenLimitMode = 'my' | 'member' | 'org';

const MODE_CONFIG: Record<TokenLimitMode, { header: string; subject: string }> = {
  my: { header: '나의 토큰 사용 제한 설정', subject: '자신의' },
  member: { header: '멤버 토큰 사용 제한 설정', subject: '선택된 멤버 개인의' },
  org: { header: '조직 토큰 사용 제한 설정', subject: '조직의' },
};

interface TokenLimitSettingsProps {
  mode?: TokenLimitMode;
}

export default function TokenLimitSettings({ mode = 'my' }: TokenLimitSettingsProps) {
  const { header, subject } = MODE_CONFIG[mode];

  return (
    <div className="flex flex-col gap-1">
      {/* 헤더 */}
      <div className="bg-fill-strong rounded px-5 py-1.5">
        <span className="text-heading-small text-content-neutral">{header}</span>
      </div>

      {/* 설정 행들 */}
      <div className="flex flex-col px-4">
        <LimitRow
          title="하루 최대 토큰 비용"
          description={`${subject} 하루 최대 토큰 비용을 설정할 수 있습니다.\n비용을 초과할 경우, 토큰 비용이 발생하는 모든 기능이 정지됩니다.`}
          defaultValue={DEFAULT_DAILY_LIMIT}
          hasBorder
        />
        <LimitRow
          title="월 최대 토큰 비용"
          description={`${subject} 월 최대 토큰 비용을 설정할 수 있습니다.\n비용을 초과할 경우, 토큰 비용이 발생하는 모든 기능이 정지됩니다.`}
          defaultValue={DEFAULT_MONTHLY_LIMIT}
          hasBorder={false}
        />
      </div>
    </div>
  );
}
