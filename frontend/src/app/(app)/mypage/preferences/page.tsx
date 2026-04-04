'use client';

import { useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

import InstructionCard from '@/features/mypage/preferences/components/InstructionCard';
import InstructionInput from '@/features/mypage/preferences/components/InstructionInput';
import { promptMutations } from '@/features/mypage/preferences/queries/prompt.mutations';
import { promptQueries } from '@/features/mypage/preferences/queries/prompt.queries';

export default function PreferencesPage() {
  const queryClient = useQueryClient();
  const [isEditing, setIsEditing] = useState(false);

  // 커스텀 프롬프트 조회
  const { data, isLoading } = useQuery(promptQueries.customPrompt());
  const customPrompt = data?.custom_prompt ?? null;
  const hasPrompt = customPrompt !== null;

  // 프롬프트 저장/삭제 mutation
  const updateMutation = useMutation({
    ...promptMutations.updateCustomPrompt(),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: promptQueries.all() });
      setIsEditing(false);
    },
  });

  const handleSave = (value: string) => {
    updateMutation.mutate({ custom_prompt: value });
  };

  const handleEdit = () => {
    setIsEditing(true);
  };

  const handleDelete = () => {
    updateMutation.mutate({ custom_prompt: null });
  };

  const handleCancelEdit = () => {
    setIsEditing(false);
  };

  return (
    <section className="flex min-w-150 flex-col gap-6 px-16 pt-9 pb-30">
      <h1 className="text-heading-xlarge text-content-normal">개인 맞춤 설정</h1>

      {/* 개인 지침 섹션 */}
      <div className="flex flex-col gap-1">
        <div className="bg-fill-strong rounded-md px-5 py-1.5">
          <span className="text-heading-small text-content-neutral">프롬프트 지침</span>
        </div>

        <div className="flex flex-col px-4">
          <div className="flex flex-col gap-3 py-3">
            <div className="flex flex-col gap-1.5">
              <span className="text-heading-small text-content-normal">지침 작성</span>
              <span className="text-label-small text-content-alternative">
                컨텍스트를 설정하고 프로젝트 내에서 Catch Up이 응답하는 방식을 맞춤 설정하세요.
              </span>
            </div>

            {/* 로딩 상태 */}
            {isLoading && (
              <div className="border-edge-neutral bg-fill-normal flex h-11.5 items-center justify-center rounded-xl border">
                <span className="text-body-small text-content-assistive">불러오는 중...</span>
              </div>
            )}

            {/* 프롬프트가 없거나 수정 중일 때만 입력창 표시 */}
            {!isLoading && (!hasPrompt || isEditing) && (
              <InstructionInput
                key={isEditing ? 'edit' : 'new'}
                onSave={handleSave}
                defaultValue={isEditing ? (customPrompt ?? '') : ''}
                defaultActive={isEditing}
                onCancelEdit={handleCancelEdit}
                isPending={updateMutation.isPending}
              />
            )}

            {/* 저장된 프롬프트 카드 (수정 중이 아닐 때만 표시) */}
            {!isLoading && hasPrompt && !isEditing && (
              <InstructionCard content={customPrompt} onEdit={handleEdit} onDelete={handleDelete} />
            )}
          </div>
        </div>
      </div>
    </section>
  );
}
