'use client';

import { useRef } from 'react';
import ArrowRight from '/public/icons/icon/arrow_right2.svg';
import { useEscapeKey } from '@/hooks/useEscapeKey';
import { useOutsideClick } from '@/hooks/useOutsideClick';

interface TeamSpaceModalProps {
  onClose: () => void;
}

const TeamSpaceModal = ({ onClose }: TeamSpaceModalProps) => {
  const modalRef = useRef<HTMLDivElement>(null);
  useEscapeKey(onClose);
  useOutsideClick(modalRef, onClose);

  return (
    <div
      ref={modalRef}
      onClick={(e) => e.stopPropagation()}
      className="shadow-dropdown-menu border-neutral-4 flex max-h-95 w-62.5 flex-col gap-1 overflow-y-auto rounded-2xl border bg-white px-1.5 py-2"
    >
      <button className="icon-button-only-gray flex w-55 cursor-pointer items-center gap-2.5 rounded-lg p-2">
        <ArrowRight className="text-gray-70 h-6 w-6 flex-shrink-0" />
        <span className="text-body-small text-gray-80 min-w-0 truncate">팀스페이스 text text text text</span>
      </button>
      <button className="icon-button-only-gray flex w-55 cursor-pointer items-center gap-2.5 rounded-lg p-2">
        <ArrowRight className="text-gray-70 h-6 w-6 flex-shrink-0" />
        <span className="text-body-small text-gray-80 min-w-0 truncate">팀스페이스 text text text text</span>
      </button>
    </div>
  );
};

export default TeamSpaceModal;
