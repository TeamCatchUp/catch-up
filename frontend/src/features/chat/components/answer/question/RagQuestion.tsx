'use client';

import { useState } from 'react';

import type { QAPair } from '@/features/chat/utils/render/chat';

import EditMessageInput from './EditMessageInput';
import QuestionActions from './QuestionActions';

interface RagQuestionProps {
  currentQA: QAPair | undefined;
  isLastPage: boolean;
  onSubmitEdit: (messageId: string, newContent: string) => Promise<void>;
}

export default function RagQuestion({ currentQA, isLastPage, onSubmitEdit }: RagQuestionProps) {
  const [editingMessageId, setEditingMessageId] = useState<string | null>(null);

  const questionId = currentQA?.question.id ?? null;
  const questionContent = currentQA?.question.content ?? '';
  const isEditing = questionId !== null && editingMessageId === questionId;

  if (!currentQA || !questionId) return null;

  if (isEditing) {
    const handleSubmit = async (newContent: string) => {
      await onSubmitEdit(questionId, newContent);
      setEditingMessageId(null);
    };

    return (
      <EditMessageInput
        initialContent={questionContent}
        onCancel={() => setEditingMessageId(null)}
        onSubmit={handleSubmit}
      />
    );
  }

  return (
    <div className="group flex items-end justify-end gap-2.5">
      <div className="hidden group-hover:flex">
        <QuestionActions
          content={questionContent}
          onEdit={isLastPage ? () => setEditingMessageId(questionId) : undefined}
        />
      </div>
      <div className="bg-fill-strong text-body-small text-content-neutral wrap-break-words max-w-135 rounded-2xl px-4 py-3 whitespace-pre-wrap">
        {questionContent}
      </div>
    </div>
  );
}
