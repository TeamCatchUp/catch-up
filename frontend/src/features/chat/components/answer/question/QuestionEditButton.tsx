import EditPencil from '@/public/icons/icon/edit_pencil.svg';
import { cn } from '@/shared/utils/cn';

interface QuestionEditButtonProps {
  onClick: () => void;
}

const QuestionEditButton = ({ onClick }: QuestionEditButtonProps) => {
  return (
    <button
      type="button"
      onClick={onClick}
      className={cn(
        'border-neutral-3 box-button-outline-gray',
        'hidden shrink-0 group-hover:inline-flex',
        'cursor-pointer justify-center gap-1 rounded-lg border px-2 py-1',
      )}
    >
      <EditPencil className="text-gray-70 h-5 w-5" />
      <span className="text-body-xsmall text-gray-80 whitespace-nowrap">수정하기</span>
    </button>
  );
};

export default QuestionEditButton;
