import Link from 'next/link';

import { TUTORIALS } from '@/features/mypage/help/constants/tutorialData';
import ArrowLeft from '@/public/icons/icon/arrow_left.svg';
import ArrowRight from '@/public/icons/icon/arrow_right.svg';
import { cn } from '@/shared/utils/cn';

interface TutorialPaginationProps {
  currentId: number;
}

export default function TutorialPagination({ currentId }: TutorialPaginationProps) {
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
            <ArrowLeft className="text-content-alternative h-6 w-6" />
          </Link>
        ) : (
          <span className="flex size-6 items-center justify-center">
            <ArrowLeft className="text-content-assistive h-6 w-6" />
          </span>
        )}

        {TUTORIALS.map((tutorial) => (
          <Link
            key={tutorial.id}
            href={`/mypage/help/tutorial/${tutorial.id}`}
            className={cn(
              'rounded-md2 text-body-small flex size-7.5 items-center justify-center',
              tutorial.id === currentId
                ? 'bg-fill-interaction-hover text-content-normal'
                : 'hover:bg-fill-interaction-hover text-content-alternative',
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
            <ArrowRight className="text-content-alternative h-6 w-6" />
          </Link>
        ) : (
          <span className="flex size-6 items-center justify-center">
            <ArrowRight className="text-content-assistive h-6 w-6" />
          </span>
        )}
      </nav>

      {/* 목록으로 버튼 */}
      <Link
        href="/mypage/help"
        className="border-edge-neutral hover:bg-fill-interaction-hover bg-fill-normal flex h-10 items-center justify-center rounded-lg border px-4 py-1.5 transition-colors"
      >
        <span className="text-body-medium text-content-alternative">목록으로</span>
      </Link>
    </div>
  );
}
