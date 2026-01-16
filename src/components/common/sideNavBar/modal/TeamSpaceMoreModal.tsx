'use client';

import { useRef } from 'react';
import GroupAdd from '/public/icons/icon/group_add.svg';
import Settings from '/public/icons/icon/settings.svg';
import { useEscapeKey } from '@/hooks/useEscapeKey';
import { useOutsideClick } from '@/hooks/useOutsideClick';

interface TeamSpaceMoreModalProps {
  onClose: () => void;
}

const TeamSpaceMoreModal = ({ onClose }: TeamSpaceMoreModalProps) => {
  const modalRef = useRef<HTMLDivElement>(null);

  useEscapeKey(onClose);
  useOutsideClick(modalRef, onClose);

  return (
    <div
      ref={modalRef}
      className="shadow-dropdown-menu border-neutral-4 flex h-25 w-62.5 flex-col gap-1 rounded-2xl border bg-white px-1.5 py-2"
    >
      <div className="text-button-secondary-mono flex cursor-pointer items-center gap-2.5 rounded-lg! p-2">
        <GroupAdd onClick={onClose} className="text-gray-70 h-6 w-6" />
        <span className="text-body-small text-gray-80">팀원 추가</span>
      </div>
      <div className="text-button-secondary-mono flex cursor-pointer items-center gap-2.5 rounded-lg! p-2">
        <Settings onClick={onClose} className="text-gray-70 h-6 w-6" />
        <span className="text-body-small text-gray-80">팀스페이스 설정</span>
      </div>
    </div>
  );
};

export default TeamSpaceMoreModal;
