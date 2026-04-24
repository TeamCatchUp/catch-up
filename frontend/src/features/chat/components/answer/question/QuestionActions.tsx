'use client';

import { toast } from 'sonner';

import Copy from '@/public/icons/icon/copy.svg';
import EditPencil from '@/public/icons/icon/edit_pencil.svg';
import { Button } from '@/shared/components/ui/button';
import { Tooltip, TooltipContent, TooltipTrigger } from '@/shared/components/ui/tooltip';

interface QuestionActionsProps {
  content: string;
  onEdit: () => void;
}

export default function QuestionActions({ content, onEdit }: QuestionActionsProps) {
  const handleCopy = () => {
    navigator.clipboard.writeText(content);
    toast('질문이 복사되었습니다.');
  };

  return (
    <div className="flex items-center gap-1">
      <Tooltip>
        <TooltipTrigger asChild>
          <Button variant="icon-only-gray" size="md" type="button" onClick={onEdit} aria-label="질문 수정하기">
            <EditPencil className="h-6 w-6" />
          </Button>
        </TooltipTrigger>
        <TooltipContent side="bottom">수정하기</TooltipContent>
      </Tooltip>
      <Tooltip>
        <TooltipTrigger asChild>
          <Button variant="icon-only-gray" size="md" type="button" onClick={handleCopy} aria-label="질문 복사하기">
            <Copy className="h-6 w-6" />
          </Button>
        </TooltipTrigger>
        <TooltipContent side="bottom">복사하기</TooltipContent>
      </Tooltip>
    </div>
  );
}
