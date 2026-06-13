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

export default function TutorialHeader({ prevLabel, prevHref, currentLabel }: TutorialHeaderProps) {
  const router = useRouter();

  return (
    <div className="border-b-line-normal-neutral bg-fill-normal-normal z-base sticky top-0 flex h-13 shrink-0 items-center justify-between border-b px-16 py-2">
      {/* 좌측: 브레드크럼 */}
      <div className="flex items-center justify-center">
        <Link
          href={prevHref}
          className="hover:bg-fill-normal-interaction-hover flex items-center gap-1.5 rounded-xl px-2 py-1"
        >
          <Help className="text-text-normal-alternative h-5 w-5" />
          <span className="text-heading-small text-text-normal-alternative">{prevLabel}</span>
        </Link>
        <ArrowRight2 className="text-text-normal-alternative h-5 w-5" />
        <span className="text-heading-small text-text-normal-normal max-w-50 truncate px-2 py-1">{currentLabel}</span>
      </div>

      {/* 우측: 액션 버튼 */}
      <div className="flex items-center gap-1.5">
        <button
          onClick={() => router.push('/search')}
          className="border-line-normal-neutral hover:border-line-normal-normal hover:bg-fill-normal-interaction-hover active:border-line-normal-strong active:bg-fill-normal-interaction-pressed bg-fill-normal-normal flex cursor-pointer items-center gap-1.5 rounded-lg border px-2.5 py-1.5 transition-colors"
        >
          <Add className="text-icon-normal-normal h-5 w-5" />
          <span className="text-body-small text-text-normal-neutral whitespace-nowrap">새 업무 질문</span>
        </button>
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <button className="border-line-normal-neutral hover:border-line-normal-normal hover:bg-fill-normal-interaction-hover active:border-line-normal-strong active:bg-fill-normal-interaction-pressed data-[state=open]:border-line-normal-normal data-[state=open]:bg-fill-normal-interaction-hover bg-fill-normal-normal cursor-pointer rounded-lg border px-1.5 py-1.5 transition-colors">
              <Kebeb className="text-icon-normal-normal h-6 w-6" />
            </button>
          </DropdownMenuTrigger>
          <MoreButtonContent />
        </DropdownMenu>
      </div>
    </div>
  );
}
