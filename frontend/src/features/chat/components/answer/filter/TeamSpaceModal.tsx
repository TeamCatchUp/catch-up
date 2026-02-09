'use client';

import { useRef } from 'react';

import type { TeamSpace } from '@/features/chat/constants/config';
import { useEscapeKey } from '@/shared/hooks/useEscapeKey';
import { useOutsideClick } from '@/shared/hooks/useOutsideClick';
import { cn } from '@/shared/utils/cn';

import ArrowRight from '/public/icons/icon/arrow_right2.svg';

interface TeamSpaceModalProps {
  onClose: () => void;
  teamSpaces: TeamSpace[];
  selectedId: string;
  onSelect: (team: TeamSpace) => void;
}

const TeamSpaceModal = ({ onClose, teamSpaces, selectedId, onSelect }: TeamSpaceModalProps) => {
  const modalRef = useRef<HTMLDivElement>(null);
  useEscapeKey(onClose);
  useOutsideClick(modalRef, onClose);

  return (
    <div
      ref={modalRef}
      onClick={(e) => e.stopPropagation()}
      className="shadow-dropdown-menu border-neutral-4 flex max-h-95 w-62.5 flex-col gap-1 overflow-y-auto rounded-2xl border bg-white px-1.5 py-2"
    >
      {teamSpaces.map((team) => {
        const isSelected = team.id === selectedId;

        return (
          <button
            key={team.id}
            onClick={() => {
              onSelect(team);
              onClose();
            }}
            className={cn(
              'icon-button-only-gray flex w-58.25 cursor-pointer items-center gap-2.5 rounded-lg p-2',
              isSelected && 'bg-neutral-3',
            )}
          >
            <ArrowRight className="text-gray-70 h-6 w-6 shrink-0" />
            <span className="text-body-small text-gray-80 min-w-0 truncate">{team.name}</span>
          </button>
        );
      })}
    </div>
  );
};

export default TeamSpaceModal;
