'use client';

import clsx from 'clsx';
import { useRef, useState } from 'react';
import ArrowRight from '/public/icons/icon/arrow_right2.svg';
import { useEscapeKey } from '@/hooks/shared/useEscapeKey';
import { useOutsideClick } from '@/hooks/shared/useOutsideClick';

interface TeamSpaceModalProps {
  onClose: () => void;
  teamSpaces: TeamSpace[];
  selectedId: string;
  onSelect: (team: TeamSpace) => void;
}

const TEAM_SPACES = [
  { id: 'fe', name: 'Catch Up | FE' },
  { id: 'be', name: 'Catch Up | BE' },
  { id: 'pm', name: 'Catch Up | 기획' },
  { id: 'design', name: 'Catch Up | Design' },
] as const;

type TeamSpace = (typeof TEAM_SPACES)[number];

const TeamSpaceModal = ({ onClose, teamSpaces, selectedId, onSelect }: TeamSpaceModalProps) => {
  const modalRef = useRef<HTMLDivElement>(null);
  useEscapeKey(onClose);
  useOutsideClick(modalRef, onClose);

  const [selectedTeamSpaceId, setSelectedTeamSpaceId] = useState<string>(TEAM_SPACES[0].id);
  const selectedTeamSpace = TEAM_SPACES.find((t) => t.id === selectedTeamSpaceId) ?? TEAM_SPACES[0];

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
            className={clsx(
              'icon-button-only-gray flex w-58.25 cursor-pointer items-center gap-2.5 rounded-lg p-2',
              isSelected && 'bg-neutral-3',
            )}
          >
            <ArrowRight className="text-gray-70 h-6 w-6 flex-shrink-0" />
            <span className="text-body-small text-gray-80 min-w-0 truncate">{team.name}</span>
          </button>
        );
      })}
    </div>
  );
};

export default TeamSpaceModal;
