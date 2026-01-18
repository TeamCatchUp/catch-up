import clsx from 'clsx';
import { useState, useRef } from 'react';
import AI from '/public/icons/icon/ai.svg';
import Add from '/public/icons/icon/add_small.svg';
import Search from '/public/icons/icon/search.svg';
import Close from '/public/icons/icon/cancel.svg';
import Chat from '/public/icons/icon/chat.svg';

const CatchAssistantModal = () => {
  return (
    <div className="shadow-modal border-neutral-4 flex flex-col gap-4 rounded-3xl border bg-white px-3 py-4">
      {/* 헤더 */}
      <div className="flex items-center justify-between">
        <div className="flex gap-2 px-1.5">
          <AI className="h-7 w-7" />
          <span className="text-heading-large text-gray-70">캐치스턴트 히스토리</span>
        </div>
        <div className="flex gap-1.5">
          <button className="capsule-button-outline-border flex gap-1.5 px-3 py-1.5">
            <Add className="h-5 w-5 text-blue-50" />
            <span className="text-body-small text-blue-55">새 업무 질문</span>
          </button>
          <button className="p-1.5">
            <Search className="h-6 w-6" />
          </button>
          <button className="p-1.5">
            <Close className="h-6 w-6" />
          </button>
        </div>
      </div>
    </div>
  );
};
