'use client';

import { useState } from 'react';
import clsx from 'clsx';
import EditPencil from '/public/icons/icon/edit_pencil.svg';
import EditMessageInput from './EditMessageInput';
import type { QAPair } from '@/util/ragAnswer/chat';

interface RagQuestionProps {
  currentQA: QAPair | undefined;
  isLastPage: boolean;
  onSubmitEdit: (messageId: string, newContent: string) => Promise<void>;
}

const RagQuestion = ({ currentQA, isLastPage, onSubmitEdit }: RagQuestionProps) => {
  const [editingMessageId, setEditingMessageId] = useState<string | null>(null);

  if (!currentQA) return null;

  const isEditing = editingMessageId === currentQA.question.id;

  if (isEditing) {
    const handleSubmit = async (newContent: string) => {
      await onSubmitEdit(currentQA.question.id, newContent);
      setEditingMessageId(null);
    };

    return (
      <EditMessageInput
        initialContent={currentQA.question.content}
        onCancel={() => setEditingMessageId(null)}
        onSubmit={handleSubmit}
      />
    );
  }

  return (
    <div className="group relative max-w-full">
      <span className="text-heading-xlarge text-gray-70 mr-5">
        {currentQA.question.content}
      </span>
      {isLastPage && (
        <button
          onClick={() => setEditingMessageId(currentQA.question.id)}
          className={clsx(
            'border-neutral-3 box-button-outline-gray',
            'hidden group-hover:inline-flex',
            'translate-y-1 cursor-pointer justify-center gap-1 rounded-lg border px-2 py-1',
          )}
        >
          <EditPencil className="text-gray-70 h-5 w-5" />
          <span className="text-body-xsmall text-gray-80 whitespace-nowrap">수정하기</span>
        </button>
      )}
    </div>
  );
};

export default RagQuestion;
