import Link from 'next/link';
import { useRouter } from 'next/navigation';

import Add from '@/public/icons/icon/add_small.svg';
import ArrowRight2 from '@/public/icons/icon/arrow_right2.svg';
import Help from '@/public/icons/icon/help.svg';
import Kebeb from '@/public/icons/icon/kebeb 2.svg';
import { MoreButtonContent } from '@/shared/components/layout/topNavbar/MoreButtonModal';
import { DropdownMenu, DropdownMenuTrigger } from '@/shared/components/ui/dropdown-menu';

interface TutorialHeaderProps {
  prevLabel: string;
  prevHref: string;
  currentLabel: string;
}

const TutorialHeader = ({ prevLabel, prevHref, currentLabel }: TutorialHeaderProps) => {
  const router = useRouter();

  return (
    <div className="border-b-neutral-3 sticky top-0 z-10 flex h-13 shrink-0 items-center justify-between border-b bg-white px-16 py-2">
      {/* 좌측: 브레드크럼 */}
      <div className="flex items-center justify-center">
        <Link
          href={prevHref}
          className="flex items-center gap-1.5 rounded-xl px-2 py-1 hover:bg-neutral-2"
        >
          <Help className="h-5 w-5 text-gray-50" />
          <span className="text-heading-small text-gray-50">{prevLabel}</span>
        </Link>
        <ArrowRight2 className="h-5 w-5 text-gray-50" />
        <span className="text-heading-small max-w-50 truncate px-2 py-1 text-gray-80">
          {currentLabel}
        </span>
      </div>

      {/* 우측: 액션 버튼 */}
      <div className="flex items-center gap-1.5">
        <button
          onClick={() => router.push('/search')}
          className="border-neutral-3 hover:border-neutral-4 hover:bg-neutral-2 active:border-neutral-5 active:bg-neutral-3 flex cursor-pointer items-center gap-1.5 rounded-lg border bg-white px-2.5 py-1.5 transition-colors"
        >
          <Add className="h-5 w-5 text-gray-70" />
          <span className="text-body-small whitespace-nowrap text-gray-70">새 업무 질문</span>
        </button>
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <button className="border-neutral-3 hover:border-neutral-4 hover:bg-neutral-2 active:border-neutral-5 active:bg-neutral-3 data-[state=open]:border-neutral-4 data-[state=open]:bg-neutral-2 cursor-pointer rounded-lg border bg-white px-1.5 py-1.5 transition-colors">
              <Kebeb className="h-6 w-6 text-gray-70" />
            </button>
          </DropdownMenuTrigger>
          <MoreButtonContent />
        </DropdownMenu>
      </div>
    </div>
  );
};

export default TutorialHeader;
