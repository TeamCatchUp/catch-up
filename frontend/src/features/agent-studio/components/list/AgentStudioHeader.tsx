import KebabHorizontalIcon from '@/public/icons/icon/kebab_horizontal.svg';
import LightbulbIcon from '@/public/icons/icon/lightbulb.svg';
import { MoreButtonContent } from '@/shared/components/layout/topNavbar/MoreButtonModal';
import { Button } from '@/shared/components/ui/button';
import { DropdownMenu, DropdownMenuTrigger } from '@/shared/components/ui/dropdown-menu';

export default function AgentStudioHeader() {
  return (
    <header className="border-line-normal-neutral flex h-13 shrink-0 items-center justify-between border-b px-16 py-2">
      <div className="flex items-center gap-2">
        <LightbulbIcon className="text-icon-normal-normal size-6" aria-hidden="true" />
        <span className="text-heading-medium text-text-normal-normal">Agent Studio</span>
      </div>
      <DropdownMenu>
        <DropdownMenuTrigger asChild>
          <Button variant="icon-only-gray" size="md" aria-label="더보기 메뉴">
            <KebabHorizontalIcon className="size-6" aria-hidden="true" />
          </Button>
        </DropdownMenuTrigger>
        <MoreButtonContent />
      </DropdownMenu>
    </header>
  );
}
