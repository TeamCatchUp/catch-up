'use client';

import { useState } from 'react';

import { Switch } from '@/shared/components/ui/switch';
import { cn } from '@/shared/utils/cn';

/**
 * 답변 톤 옵션 목록
 */
const TONE_OPTIONS = ['캐주얼', '기본', '격식'] as const;

/**
 * 이모지 사용 강도 옵션 목록
 */
const EMOJI_OPTIONS = ['없음', '기본', '많음'] as const;

type ToneOption = (typeof TONE_OPTIONS)[number];
type EmojiOption = (typeof EMOJI_OPTIONS)[number];

/**
 * 개인 맞춤 설정 화면을 렌더링
 */
export default function PreferencesPage() {
  const [tone, setTone] = useState<ToneOption>('기본');
  const [emojiLevel, setEmojiLevel] = useState<EmojiOption>('없음');
  const [useCustomPrompt, setUseCustomPrompt] = useState(false);
  const [customPrompt, setCustomPrompt] = useState('');

  return (
    <section className="border-neutral-3 mx-16 mt-6 mb-25 rounded-xl border bg-white p-6">
      <div className="mb-6">
        <h1 className="text-heading-large text-gray-80">개인 맞춤 설정</h1>
        <p className="text-body-small text-gray-60 mt-2">답변 스타일과 프롬프트 지침을 개인 설정으로 저장합니다.</p>
      </div>

      <div className="flex flex-col gap-6">
        <div className="border-neutral-3 rounded-lg border p-4">
          <div className="text-heading-small text-gray-80">답변 톤</div>
          <div className="mt-3 flex gap-2">
            {TONE_OPTIONS.map((option) => (
              <button
                key={option}
                type="button"
                onClick={() => setTone(option)}
                className={cn(
                  'text-body-small rounded-md border px-3 py-2',
                  tone === option ? 'border-blue-40 bg-blue-1 text-blue-60' : 'border-neutral-3 text-gray-70 bg-white',
                )}
              >
                {option}
              </button>
            ))}
          </div>
        </div>

        <div className="border-neutral-3 rounded-lg border p-4">
          <div className="text-heading-small text-gray-80">이모지 사용 정도</div>
          <div className="mt-3 flex gap-2">
            {EMOJI_OPTIONS.map((option) => (
              <button
                key={option}
                type="button"
                onClick={() => setEmojiLevel(option)}
                className={cn(
                  'text-body-small rounded-md border px-3 py-2',
                  emojiLevel === option
                    ? 'border-blue-40 bg-blue-1 text-blue-60'
                    : 'border-neutral-3 text-gray-70 bg-white',
                )}
              >
                {option}
              </button>
            ))}
          </div>
        </div>

        <div className="border-neutral-3 rounded-lg border p-4">
          <div className="flex items-center justify-between">
            <div>
              <div className="text-heading-small text-gray-80">커스텀 프롬프트 지침</div>
              <div className="text-body-xsmall text-gray-60 mt-1">응답에 반드시 반영할 개인 지침을 설정합니다.</div>
            </div>
            <Switch checked={useCustomPrompt} onCheckedChange={setUseCustomPrompt} />
          </div>

          <textarea
            value={customPrompt}
            onChange={(e) => setCustomPrompt(e.target.value)}
            disabled={!useCustomPrompt}
            placeholder="예: 답변은 짧고 명확하게, 마지막에 체크리스트 형태로 정리"
            className="border-neutral-3 text-body-small text-gray-80 disabled:bg-neutral-2 mt-3 h-32 w-full resize-none rounded-md border bg-white px-3 py-2"
          />
        </div>
      </div>

      <div className="mt-6 flex justify-end">
        <button type="button" className="box-button-solid-primary h-10 px-4 py-2 text-white">
          저장
        </button>
      </div>
    </section>
  );
}
