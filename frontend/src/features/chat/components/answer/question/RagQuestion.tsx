'use client';

import { useState } from 'react';

import type { QAPair } from '@/features/chat/utils/render/chat';

import CollapsibleQuestionText from './CollapsibleQuestionText';
import EditMessageInput from './EditMessageInput';
import QuestionEditButton from './QuestionEditButton';

interface RagQuestionProps {
  currentQA: QAPair | undefined;
  isLastPage: boolean;
  onSubmitEdit: (messageId: string, newContent: string) => Promise<void>;
}

const RagQuestion = ({ currentQA, isLastPage, onSubmitEdit }: RagQuestionProps) => {
  const [editingMessageId, setEditingMessageId] = useState<string | null>(null);

  const questionId = currentQA?.question.id ?? null;
  const questionContent = currentQA?.question.content ?? '';
  const questionRenderKey = `${questionId}:${questionContent}`;
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
    <div className="group relative flex max-w-full items-start gap-1">
      <div className="relative min-w-0 flex-1">
        <CollapsibleQuestionText key={questionRenderKey} content={questionContent} />
      </div>

      {isLastPage && (
        <QuestionEditButton onClick={() => setEditingMessageId(questionId)} />
      )}
    </div>
  );
};

export default RagQuestion;
