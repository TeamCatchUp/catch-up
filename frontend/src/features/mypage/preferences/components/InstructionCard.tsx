'use client';

import IconDelete from '@/public/icons/icon/delete.svg';
import IconEditSquare from '@/public/icons/icon/edit_square.svg';
import IconKebab from '@/public/icons/icon/kebab.svg';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/shared/components/ui/dropdown-menu';

interface InstructionCardProps {
  content: string;
  onEdit: () => void;
  onDelete: () => void;
}

export default function InstructionCard({ content, onEdit, onDelete }: InstructionCardProps) {
  return (
    <div className="border-edge-neutral bg-fill-normal flex max-h-[160px] min-h-11.5 items-start gap-6 overflow-y-auto rounded-xl border px-4 py-3">
      <p className="text-body-small text-icon-normal w-full wrap-break-word whitespace-pre-wrap">{content}</p>

      <DropdownMenu>
        <DropdownMenuTrigger asChild>
          <button
            type="button"
            className="active:bg-fill-interaction-pressed hover:bg-fill-interaction-hover sticky top-0 flex size-10 shrink-0 cursor-pointer items-center justify-center rounded-lg p-1.5"
          >
            <IconKebab className="text-icon-normal size-6" />
          </button>
        </DropdownMenuTrigger>
        <DropdownMenuContent align="end" sideOffset={4} className="w-[250px] min-w-0">
          <DropdownMenuItem onClick={onEdit} className="gap-2.5">
            <IconEditSquare className="size-6 shrink-0" />
            맞춤형 지침 수정하기
          </DropdownMenuItem>
          <DropdownMenuSeparator />
          <DropdownMenuItem onClick={onDelete} className="gap-2.5 text-red-50">
            <IconDelete className="size-6 shrink-0" />
            맞춤형 지침 삭제하기
          </DropdownMenuItem>
        </DropdownMenuContent>
      </DropdownMenu>
    </div>
  );
}
