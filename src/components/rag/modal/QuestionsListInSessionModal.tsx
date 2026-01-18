'use client';

import { useState, useRef } from 'react';
import List from '/public/icons/icon/list.svg';
import { useEscapeKey } from '@/hooks/useEscapeKey';
import { useOutsideClick } from '@/hooks/useOutsideClick';

interface QuestionsListInSessionModalProps {
  onClose: () => void;
}

// 질문 목록 더미데이터
const questions = [
  '지금 일본 시장 진출 프로젝트에서 가장 큰 걸림돌(Block1)',
  '지금 일본 시장 진출 프로젝트에서 가장 큰 걸림돌(Block2)',
  '지금 일본 시장 진출 프로젝트에서 가장 큰 걸림돌(Block3)',
  '지금 일본 시장 진출 프로젝트에서 가장 큰 걸림돌(Block4)',
  '지금 일본 시장 진출 프로젝트에서 가장 큰 걸림돌(Block5)',
  '지금 일본 시장 진출 프로젝트에서 가장 큰 걸림돌(Block6)',
  '지금 일본 시장 진출 프로젝트에서 가장 큰 걸림돌(Block7)',
  '지금 일본 시장 진출 프로젝트에서 가장 큰 걸림돌(Block8)',
  '지금 일본 시장 진출 프로젝트에서 가장 큰 걸림돌(Block9)',
  '지금 일본 시장 진출 프로젝트에서 가장 큰 걸림돌(Block9)',
];

const QuestionsListInSessionModal = ({ onClose }: QuestionsListInSessionModalProps) => {
  const modalRef = useRef<HTMLDivElement>(null);
  useEscapeKey(onClose);
  useOutsideClick(modalRef, onClose);

  return (
    <div
      ref={modalRef}
      className="shadow-dropdown-menu border-neutral-5 flex max-h-125 w-95 flex-col gap-4 rounded-2xl border bg-white py-4"
    >
      {/* 헤더 */}
      <div className="flex items-center gap-2 px-5">
        <List className="text-gray-70 h-6 w-6" />
        <span className="text-heading-medium text-gray-80 relative top-px">대화 내 질문 목록</span>
        <span className="text-heading-medium text-blue-55 relative top-px">{questions.length}</span>
      </div>
      {/* 질문 목록 */}
      <div className="border-t-neutral-3 overflow-y-auto border-t pt-3">
        <div className="flex flex-col gap-2 px-4">
          {questions.map((question, idx) => (
            <button
              key={idx}
              className="text-button-secondary-mono rounded-md2! flex h-10 w-87 cursor-pointer items-center px-2.5 py-1"
            >
              <span className="text-body-small text-gray-80 truncate">{question}</span>
            </button>
          ))}
        </div>
      </div>
    </div>
  );
};

export default QuestionsListInSessionModal;
