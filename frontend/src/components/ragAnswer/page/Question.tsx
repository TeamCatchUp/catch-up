/**
 * Question Compound Component
 * 질문 표시 및 수정 기능 (Text, EditButton, EditForm)
 */

'use client';

import type { PropsWithChildren } from 'react';
import clsx from 'clsx';
import EditPencil from '/public/icons/icon/edit_pencil.svg';
import EditMessageInput from '@/components/ragAnswer/components/EditMessageInput';
import { useRagPageContext } from './Context';

/** Question Root - 편집 모드에 따라 텍스트/폼 전환 */
const Question = ({ children }: PropsWithChildren) => {
  const { pagination, ui } = useRagPageContext();
  const { currentQA } = pagination;

  if (!currentQA) return null;

  const isEditing = ui.editingMessageId === currentQA.question.id;

  if (isEditing) {
    return <QuestionEditForm />;
  }

  return (
    <div className="group relative max-w-full">
      {children}
    </div>
  );
};

/** 질문 텍스트 표시 */
const QuestionText = () => {
  const { pagination } = useRagPageContext();
  const { currentQA } = pagination;

  if (!currentQA) return null;

  return (
    <span className="text-heading-xlarge text-gray-70 mr-5">
      {currentQA.question.content}
    </span>
  );
};

const QuestionEditButton = () => {
  const { pagination, ui } = useRagPageContext();
  const { currentQA, qaPairs, currentPage } = pagination;

  if (!currentQA) return null;

  // 마지막 페이지에서만 수정 버튼 표시
  const isLastPage = currentPage === qaPairs.length - 1;
  if (!isLastPage) return null;

  return (
    <button
      onClick={() => ui.setEditingMessageId(currentQA.question.id)}
      className={clsx(
        'border-neutral-3 box-button-outline-gray',
        'hidden group-hover:inline-flex',
        'translate-y-1 cursor-pointer justify-center gap-1 rounded-lg border px-2 py-1',
      )}
    >
      <EditPencil className="text-gray-70 h-5 w-5" />
      <span className="text-body-xsmall text-gray-80 whitespace-nowrap">수정하기</span>
    </button>
  );
};

const QuestionEditForm = () => {
  const { pagination, ui, chat } = useRagPageContext();
  const { currentQA } = pagination;

  if (!currentQA) return null;

  const handleSubmit = async (newContent: string) => {
    await chat.submitEdit(currentQA.question.id, newContent);
    ui.setEditingMessageId(null);
  };

  return (
    <EditMessageInput
      initialContent={currentQA.question.content}
      onCancel={() => ui.setEditingMessageId(null)}
      onSubmit={handleSubmit}
    />
  );
};

/** Compound Component 조립 */
Question.Text = QuestionText;
Question.EditButton = QuestionEditButton;
Question.EditForm = QuestionEditForm;

export default Question;
