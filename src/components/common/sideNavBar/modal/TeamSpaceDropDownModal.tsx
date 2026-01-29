'use client';

import { useRef } from 'react';
import ArrowRight from '/public/icons/icon/arrow_right2.svg';
import AddHome from '/public/icons/icon/add_home.svg';
import { useEscapeKey } from '@/hooks/useEscapeKey';
import { useOutsideClick } from '@/hooks/useOutsideClick';

interface TeamSpaceDropDownModalProps {
  onClose: () => void;
}

const TeamSpaceDropDownModal = ({ onClose }: TeamSpaceDropDownModalProps) => {
  const modalRef = useRef<HTMLDivElement>(null);

  useEscapeKey(onClose);
  useOutsideClick(modalRef, onClose);

  return (
    <div
      ref={modalRef}
      className="shadow-dropdown-menu border-neutral-4 flex max-h-95 w-62.5 flex-col items-center gap-2 rounded-2xl border bg-white px-1.5 py-2"
    >
      {/* 팀스페이스 목록 */}
      <div className="flex w-59.5 flex-col gap-1">
        <div className="icon-button-only-gray flex cursor-pointer items-center gap-2.5 p-2">
          <ArrowRight className="text-gray-70 h-6 w-6" />
          <span className="text-body-small text-gray-80">Catch Up | FE</span>
        </div>
        <div className="icon-button-only-gray flex cursor-pointer items-center gap-2.5 p-2">
          <ArrowRight className="text-gray-70 h-6 w-6" />
          <span className="text-body-small text-gray-80">Catch Up | BE</span>
        </div>
        <div className="icon-button-only-gray flex cursor-pointer items-center gap-2.5 p-2">
          <ArrowRight className="text-gray-70 h-6 w-6" />
          <span className="text-body-small text-gray-80">Catch Up | 기획</span>
        </div>
        <div className="icon-button-only-gray flex cursor-pointer items-center gap-2.5 p-2">
          <ArrowRight className="text-gray-70 h-6 w-6" />
          <span className="text-body-small text-gray-80">Catch Up | Design</span>
        </div>
      </div>
      {/* divider */}
      <div className="bg-neutral-3 h-px w-55" />
      {/* 팀스페이스 추가 버튼 */}
      <div className="icon-button-only-gray flex w-59.5 cursor-pointer items-center gap-2.5 p-2">
        <AddHome className="text-gray-70 h-6 w-6" />
        <span className="text-body-small text-gray-80">팀스페이스 추가</span>
      </div>
    </div>
  );
};

export default TeamSpaceDropDownModal;
