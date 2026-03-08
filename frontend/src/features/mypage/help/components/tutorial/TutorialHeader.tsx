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
    <div className="border-b-edge-neutral sticky top-0 z-10 flex h-13 shrink-0 items-center justify-between border-b bg-fill-normal px-16 py-2">
      {/* 좌측: 브레드크럼 */}
      <div className="flex items-center justify-center">
        <Link href={prevHref} className="hover:bg-fill-interaction-hover flex items-center gap-1.5 rounded-xl px-2 py-1">
          <Help className="h-5 w-5 text-content-alternative" />
          <span className="text-heading-small text-content-alternative">{prevLabel}</span>
        </Link>
        <ArrowRight2 className="h-5 w-5 text-content-alternative" />
        <span className="text-heading-small text-content-normal max-w-50 truncate px-2 py-1">{currentLabel}</span>
      </div>

      {/* 우측: 액션 버튼 */}
      <div className="flex items-center gap-1.5">
        <button
          onClick={() => router.push('/search')}
          className="border-edge-neutral hover:border-edge-normal hover:bg-fill-interaction-hover active:border-edge-strong active:bg-fill-interaction-pressed flex cursor-pointer items-center gap-1.5 rounded-lg border bg-fill-normal px-2.5 py-1.5 transition-colors"
        >
          <Add className="text-icon-normal h-5 w-5" />
          <span className="text-body-small text-content-neutral whitespace-nowrap">새 업무 질문</span>
        </button>
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <button className="border-edge-neutral hover:border-edge-normal hover:bg-fill-interaction-hover active:border-edge-strong active:bg-fill-interaction-pressed data-[state=open]:border-edge-normal data-[state=open]:bg-fill-interaction-hover cursor-pointer rounded-lg border bg-fill-normal px-1.5 py-1.5 transition-colors">
              <Kebeb className="text-icon-normal h-6 w-6" />
            </button>
          </DropdownMenuTrigger>
          <MoreButtonContent />
        </DropdownMenu>
      </div>
    </div>
  );
};

export default TutorialHeader;
