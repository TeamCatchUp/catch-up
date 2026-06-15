import Link from 'next/link';

import { SUPPORTS } from '@/features/mypage/help/constants/supportData';
import ArrowLeft from '@/public/icons/icon/arrow_left.svg';
import ArrowRight from '@/public/icons/icon/arrow_right.svg';
import { cn } from '@/shared/utils/cn';

interface SupportPaginationProps {
  currentId: number;
}

export default function SupportPagination({ currentId }: SupportPaginationProps) {
  const currentIndex = SUPPORTS.findIndex((s) => s.id === currentId);
  const hasPrev = currentIndex > 0;
  const hasNext = currentIndex < SUPPORTS.length - 1;

  return (
    <div className="flex flex-col items-center gap-6">
      <nav className="flex items-center gap-1">
        {hasPrev ? (
          <Link
            href={`/mypage/help/support/${SUPPORTS[currentIndex - 1].id}`}
            className="flex size-6 items-center justify-center"
          >
            <ArrowLeft className="text-text-normal-alternative h-6 w-6" />
          </Link>
        ) : (
          <span className="flex size-6 items-center justify-center">
            <ArrowLeft className="text-text-normal-assistive h-6 w-6" />
          </span>
        )}

        {SUPPORTS.map((support) => (
          <Link
            key={support.id}
            href={`/mypage/help/support/${support.id}`}
            className={cn(
              'rounded-md2 text-body-small flex size-7.5 items-center justify-center',
              support.id === currentId
                ? 'bg-fill-normal-interaction-hover text-text-normal-normal'
                : 'hover:bg-fill-normal-interaction-hover text-text-normal-alternative',
            )}
          >
            {support.id}
          </Link>
        ))}

        {hasNext ? (
          <Link
            href={`/mypage/help/support/${SUPPORTS[currentIndex + 1].id}`}
            className="flex size-6 items-center justify-center"
          >
            <ArrowRight className="text-text-normal-alternative h-6 w-6" />
          </Link>
        ) : (
          <span className="flex size-6 items-center justify-center">
            <ArrowRight className="text-text-normal-assistive h-6 w-6" />
          </span>
        )}
      </nav>

      <Link
        href="/mypage/help"
        className="border-line-normal-neutral hover:bg-fill-normal-interaction-hover bg-fill-normal-normal flex h-10 items-center justify-center rounded-lg border px-4 py-1.5 transition-colors"
      >
        <span className="text-body-medium text-text-normal-alternative">목록으로</span>
      </Link>
    </div>
  );
}
