import Link from 'next/link';

import { TUTORIALS } from '@/features/mypage/help/constants/tutorialData';
import ArrowLeft from '@/public/icons/icon/arrow_left.svg';
import ArrowRight from '@/public/icons/icon/arrow_right.svg';
import { cn } from '@/shared/utils/cn';

interface TutorialPaginationProps {
  currentId: number;
}

const TutorialPagination = ({ currentId }: TutorialPaginationProps) => {
  const currentIndex = TUTORIALS.findIndex((t) => t.id === currentId);
  const hasPrev = currentIndex > 0;
  const hasNext = currentIndex < TUTORIALS.length - 1;

  return (
    <div className="flex flex-col items-center gap-6">
      {/* 페이지네이션 */}
      <nav className="flex items-center gap-1">
        {hasPrev ? (
          <Link
            href={`/mypage/help/tutorial/${TUTORIALS[currentIndex - 1].id}`}
            className="flex size-6 items-center justify-center"
          >
            <ArrowLeft className="h-6 w-6 text-gray-50" />
          </Link>
        ) : (
          <span className="flex size-6 items-center justify-center">
            <ArrowLeft className="text-gray-30 h-6 w-6" />
          </span>
        )}

        {TUTORIALS.map((tutorial) => (
          <Link
            key={tutorial.id}
            href={`/mypage/help/tutorial/${tutorial.id}`}
            className={cn(
              'rounded-md2 text-body-small flex size-7.5 items-center justify-center',
              tutorial.id === currentId ? 'bg-neutral-2 text-gray-80' : 'hover:bg-neutral-2 text-gray-50',
            )}
          >
            {tutorial.id}
          </Link>
        ))}

        {hasNext ? (
          <Link
            href={`/mypage/help/tutorial/${TUTORIALS[currentIndex + 1].id}`}
            className="flex size-6 items-center justify-center"
          >
            <ArrowRight className="h-6 w-6 text-gray-50" />
          </Link>
        ) : (
          <span className="flex size-6 items-center justify-center">
            <ArrowRight className="text-gray-30 h-6 w-6" />
          </span>
        )}
      </nav>

      {/* 목록으로 버튼 */}
      <Link
        href="/mypage/help"
        className="border-neutral-3 hover:bg-neutral-2 flex h-10 items-center justify-center rounded-lg border bg-white px-4 py-1.5 transition-colors"
      >
        <span className="text-body-medium text-gray-60">목록으로</span>
      </Link>
    </div>
  );
};

export default TutorialPagination;
