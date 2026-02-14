'use client';

import { PopoverClose, PopoverContent } from '@/shared/components/ui/popover';
import { cn } from '@/shared/utils/cn';

import AddHome from '/public/icons/icon/add_home.svg';
import ArrowRight from '/public/icons/icon/arrow_right2.svg';

interface TeamSpaceItem {
  id: string;
  name: string;
}

interface TeamSpaceDropDownContentProps {
  teamSpaces: TeamSpaceItem[];
  selectedId: string;
  onSelect: (team: TeamSpaceItem) => void;
}

export function TeamSpaceDropDownContent({ teamSpaces, selectedId, onSelect }: TeamSpaceDropDownContentProps) {
  return (
    <PopoverContent
      side="right"
      align="start"
      sideOffset={8}
      className="flex max-h-95 w-62.5 flex-col items-center gap-2 px-1.5 py-2"
      onOpenAutoFocus={(e) => e.preventDefault()}
    >
      {/* 팀스페이스 목록 */}
      <div className="flex w-full flex-col gap-1">
        {teamSpaces.map((team) => {
          const isSelected = team.id === selectedId;

          return (
            <PopoverClose asChild key={team.id}>
              <button
                type="button"
                onClick={() => onSelect(team)}
                className={cn(
                  'hover:bg-neutral-2 flex h-10 cursor-pointer items-center gap-2.5 rounded-lg p-2 transition-colors',
                  isSelected && 'bg-neutral-2',
                )}
              >
                <ArrowRight className="text-gray-70 h-6 w-6" />
                <span className={cn('text-body-small text-gray-80', isSelected && 'font-semibold')}>{team.name}</span>
              </button>
            </PopoverClose>
          );
        })}
      </div>

      {/* divider */}
      <div className="bg-neutral-3 h-px w-full" />

      {/* 팀스페이스 추가 */}
      <button className="hover:bg-neutral-2 flex w-full cursor-pointer items-center gap-2.5 rounded-lg p-2 transition-colors">
        <AddHome className="text-gray-70 h-6 w-6" />
        <span className="text-body-small text-gray-80">팀스페이스 추가</span>
      </button>
    </PopoverContent>
  );
}
