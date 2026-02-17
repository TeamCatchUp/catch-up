'use client';

import { useState } from 'react';

import InstructionCard from '@/features/mypage/preferences/components/InstructionCard';
import InstructionInput from '@/features/mypage/preferences/components/InstructionInput';
import SettingDropdownRow from '@/features/mypage/preferences/components/SettingDropdownRow';
import {
  EMOJI_OPTIONS,
  type EmojiValue,
  TONE_OPTIONS,
  type ToneValue,
} from '@/features/mypage/preferences/constants/preferences';

export default function PreferencesPage() {
  const [tone, setTone] = useState<ToneValue>('default');
  const [emojiLevel, setEmojiLevel] = useState<EmojiValue>('default');
  const [instructions, setInstructions] = useState<string[]>([]);
  const [editingIndex, setEditingIndex] = useState<number | null>(null);

  const handleSaveInstruction = (value: string) => {
    if (editingIndex != null) {
      setInstructions((prev) => prev.map((item, i) => (i === editingIndex ? value : item)));
      setEditingIndex(null);
    } else {
      setInstructions((prev) => [...prev, value]);
    }
  };

  const handleEditInstruction = (index: number) => {
    setEditingIndex(index);
  };

  const handleDeleteInstruction = (index: number) => {
    setInstructions((prev) => prev.filter((_, i) => i !== index));
    if (editingIndex === index) setEditingIndex(null);
  };

  const handleCancelEdit = () => {
    setEditingIndex(null);
  };

  return (
    <section className="flex min-w-[600px] flex-col gap-6 px-16 pt-9 pb-[120px]">
      <h1 className="text-heading-xlarge text-gray-80">개인 맞춤 설정</h1>

      {/* 프롬프트 지침 섹션 */}
      <div className="flex flex-col gap-1">
        <div className="bg-neutral-1 rounded-md px-5 py-1.5">
          <span className="text-heading-small text-gray-70">프롬프트 지침</span>
        </div>

        <div className="flex flex-col px-4">
          {/* 답변 톤 */}
          <SettingDropdownRow
            label="답변 톤"
            description="AI의 말투와 표현 방식을 설정합니다."
            options={TONE_OPTIONS}
            value={tone}
            onChange={(v) => setTone(v as ToneValue)}
          />

          {/* 이모지 사용 */}
          <SettingDropdownRow
            label="이모지 사용"
            description="AI의 말투와 표현 방식을 설정합니다."
            options={EMOJI_OPTIONS}
            value={emojiLevel}
            onChange={(v) => setEmojiLevel(v as EmojiValue)}
          />

          {/* 지침 작성 */}
          <div className="flex flex-col gap-3 py-3">
            <div className="flex flex-col gap-1.5">
              <span className="text-heading-small text-gray-80">지침 작성</span>
              <span className="text-label-small text-gray-50">
                컨텍스트를 설정하고 프로젝트 내에서 Catch Up이 응답하는 방식을 맞춤 설정하세요.
              </span>
            </div>

            <InstructionInput
              key={editingIndex ?? 'new'}
              onSave={handleSaveInstruction}
              defaultValue={editingIndex != null ? instructions[editingIndex] : ''}
              defaultActive={editingIndex != null}
              onCancelEdit={handleCancelEdit}
            />

            {instructions.map((instruction, index) => (
              <InstructionCard
                key={`${index}-${instruction.slice(0, 20)}`}
                content={instruction}
                onEdit={() => handleEditInstruction(index)}
                onDelete={() => handleDeleteInstruction(index)}
              />
            ))}
          </div>
        </div>
      </div>
    </section>
  );
}
