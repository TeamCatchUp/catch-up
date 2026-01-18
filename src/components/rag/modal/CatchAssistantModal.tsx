'use client';

import { useState, useRef } from 'react';
import AI from '/public/icons/icon/ai.svg';
import Add from '/public/icons/icon/add_small.svg';
import Search from '/public/icons/icon/search.svg';
import Close from '/public/icons/icon/cancel.svg';
import Chat from '/public/icons/icon/chat.svg';
import { useEscapeKey } from '@/hooks/useEscapeKey';
import { useOutsideClick } from '@/hooks/useOutsideClick';

interface CatchAssistantModalProps {
  onClose: () => void;
}

const CatchAssistantModal = ({ onClose }: CatchAssistantModalProps) => {
  const modalRef = useRef<HTMLDivElement>(null);
  useEscapeKey(onClose);
  useOutsideClick(modalRef, onClose);

  return (
    <div
      ref={modalRef}
      className="shadow-modal border-neutral-4 flex max-h-135 w-190 flex-col gap-4 rounded-3xl border bg-white px-3 py-4"
    >
      {/* 헤더 */}
      <div className="flex items-center justify-between">
        <div className="flex gap-2 px-1.5">
          <AI className="text-gray-70 h-7 w-7" />
          <span className="text-heading-large text-gray-70">캐치스턴트 히스토리</span>
        </div>
        <div className="flex gap-1.5">
          <button className="capsule-button-outline-blue flex cursor-pointer items-center gap-1.5 px-3 py-1.5">
            <Add className="h-5 w-5 text-blue-50" />
            <span className="text-body-small text-blue-55 relative top-px">새 업무 질문</span>
          </button>
          <button className="icon-button-only-gray cursor-pointer p-1.5">
            <Search className="h-6 w-6" />
          </button>
          <button onClick={onClose} className="icon-button-only-gray cursor-pointer p-1.5">
            <Close className="h-6 w-6" />
          </button>
        </div>
      </div>

      {/* divider */}
      <div className="bg-neutral-3 relative right-3 h-px w-189.25" />

      {/* 질문 목록 */}
      <div className="flex flex-col gap-3 overflow-y-auto px-2 pb-4">
        {/* 오늘 */}
        <div className="flex flex-col gap-2.5">
          <span className="text-body-xsmall text-gray-50">오늘</span>
          <div className="flex flex-col gap-1">
            <button className="text-button-secondary-mono flex cursor-pointer items-center gap-2 rounded-xl! py-1">
              <div className="border-neutral-3 bg-neutral-1 flex h-8 w-8 items-center justify-center rounded-full border p-1.5">
                <Chat className="h-5 w-5 text-gray-50" />
              </div>
              <span className="text-body-small text-gray-80 max-w-149 truncate">
                일본 시장 진출 전체 진행 상황 요약 text text text text text text text text text text text text text text
              </span>
              <span className="text-body-xsmall text-gray-30">2025.12.14</span>
            </button>
            <button className="text-button-secondary-mono flex cursor-pointer items-center gap-2 rounded-xl! py-1">
              <div className="border-neutral-3 bg-neutral-1 flex h-8 w-8 items-center justify-center rounded-full border p-1.5">
                <Chat className="h-5 w-5 text-gray-50" />
              </div>
              <span className="text-body-small text-gray-80 max-w-149 truncate">
                일본 시장 진출 전체 진행 상황 요약 text text text text text text text text text text text text text text
              </span>
              <span className="text-body-xsmall text-gray-30">2025.12.14</span>
            </button>
          </div>
        </div>
        {/* 최근 7일 */}
        <div className="flex flex-col gap-2.5">
          <span className="text-body-xsmall text-gray-50">최근 7일</span>
          <div className="flex flex-col gap-1">
            <button className="text-button-secondary-mono flex cursor-pointer items-center gap-2 rounded-xl! py-1">
              <div className="border-neutral-3 bg-neutral-1 flex h-8 w-8 items-center justify-center rounded-full border p-1.5">
                <Chat className="h-5 w-5 text-gray-50" />
              </div>
              <span className="text-body-small text-gray-80 max-w-149 truncate">
                일본 시장 진출 전체 진행 상황 요약 text text text text text text text text text text text text text text
              </span>
              <span className="text-body-xsmall text-gray-30">2025.12.14</span>
            </button>
            <button className="text-button-secondary-mono flex cursor-pointer items-center gap-2 rounded-xl! py-1">
              <div className="border-neutral-3 bg-neutral-1 flex h-8 w-8 items-center justify-center rounded-full border p-1.5">
                <Chat className="h-5 w-5 text-gray-50" />
              </div>
              <span className="text-body-small text-gray-80 max-w-149 truncate">
                일본 시장 진출 전체 진행 상황 요약 text text text text text text text text text text text text text text
              </span>
              <span className="text-body-xsmall text-gray-30">2025.12.14</span>
            </button>
            <button className="text-button-secondary-mono flex cursor-pointer items-center gap-2 rounded-xl! py-1">
              <div className="border-neutral-3 bg-neutral-1 flex h-8 w-8 items-center justify-center rounded-full border p-1.5">
                <Chat className="h-5 w-5 text-gray-50" />
              </div>
              <span className="text-body-small text-gray-80 max-w-149 truncate">
                일본 시장 진출 전체 진행 상황 요약 text text text text text text text text text text text text text text
              </span>
              <span className="text-body-xsmall text-gray-30">2025.12.14</span>
            </button>
            <button className="text-button-secondary-mono flex cursor-pointer items-center gap-2 rounded-xl! py-1">
              <div className="border-neutral-3 bg-neutral-1 flex h-8 w-8 items-center justify-center rounded-full border p-1.5">
                <Chat className="h-5 w-5 text-gray-50" />
              </div>
              <span className="text-body-small text-gray-80 max-w-149 truncate">
                일본 시장 진출 전체 진행 상황 요약 text text text text text text text text text text text text text text
              </span>
              <span className="text-body-xsmall text-gray-30">2025.12.14</span>
            </button>
          </div>
        </div>
        {/* 이전 */}
        <div className="flex flex-col gap-2.5">
          <span className="text-body-xsmall text-gray-50">이전</span>
          <div className="flex flex-col gap-1">
            <button className="text-button-secondary-mono flex cursor-pointer items-center gap-2 rounded-xl! py-1">
              <div className="border-neutral-3 bg-neutral-1 flex h-8 w-8 items-center justify-center rounded-full border p-1.5">
                <Chat className="h-5 w-5 text-gray-50" />
              </div>
              <span className="text-body-small text-gray-80 max-w-149 truncate">
                일본 시장 진출 전체 진행 상황 요약 text text text text text text text text text text text text text text
              </span>
              <span className="text-body-xsmall text-gray-30">2025.12.14</span>
            </button>
            <button className="text-button-secondary-mono flex cursor-pointer items-center gap-2 rounded-xl! py-1">
              <div className="border-neutral-3 bg-neutral-1 flex h-8 w-8 items-center justify-center rounded-full border p-1.5">
                <Chat className="h-5 w-5 text-gray-50" />
              </div>
              <span className="text-body-small text-gray-80 max-w-149 truncate">
                일본 시장 진출 전체 진행 상황 요약 text text text text text text text text text text text text text text
              </span>
              <span className="text-body-xsmall text-gray-30">2025.12.14</span>
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};

export default CatchAssistantModal;
