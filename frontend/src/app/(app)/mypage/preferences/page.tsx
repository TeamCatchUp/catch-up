'use client';

import { useState } from 'react';

import InstructionCard from '@/features/mypage/preferences/components/InstructionCard';
import InstructionInput from '@/features/mypage/preferences/components/InstructionInput';

export default function PreferencesPage() {
  const [instructions, setInstructions] = useState<string[]>([]);
  const [editingIndex, setEditingIndex] = useState<number | null>(null);

  const hasInstruction = instructions.length > 0;
  const isEditing = editingIndex != null;

  const handleSaveInstruction = (value: string) => {
    if (isEditing) {
      setInstructions((prev) => prev.map((item, i) => (i === editingIndex ? value : item)));
      setEditingIndex(null);
    } else {
      setInstructions([value]);
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

      {/* 개인 지침 섹션 */}
      <div className="flex flex-col gap-1">
        <div className="bg-neutral-1 rounded-md px-5 py-1.5">
          <span className="text-heading-small text-gray-70">프롬프트 지침</span>
        </div>

        <div className="flex flex-col px-4">
          <div className="flex flex-col gap-3 py-3">
            <div className="flex flex-col gap-1.5">
              <span className="text-heading-small text-gray-80">지침 작성</span>
              <span className="text-label-small text-gray-50">
                컨텍스트를 설정하고 프로젝트 내에서 Catch Up이 응답하는 방식을 맞춤 설정하세요.
              </span>
            </div>

            {/* 지침이 없거나 수정 중일 때만 입력창 표시 (최대 1개) */}
            {(!hasInstruction || isEditing) && (
              <InstructionInput
                key={editingIndex ?? 'new'}
                onSave={handleSaveInstruction}
                defaultValue={isEditing ? instructions[editingIndex] : ''}
                defaultActive={isEditing}
                onCancelEdit={handleCancelEdit}
              />
            )}

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
