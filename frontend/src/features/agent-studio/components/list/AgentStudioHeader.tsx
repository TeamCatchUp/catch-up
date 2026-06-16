import KebabIcon from '@/public/icons/icon/kebeb 2.svg';
import LightbulbIcon from '@/public/icons/icon/lightbulb.svg';
import { Button } from '@/shared/components/ui/button';

export default function AgentStudioHeader() {
  return (
    <header className="border-line-normal-neutral flex h-13 shrink-0 items-center justify-between border-b px-16 py-2">
      <div className="flex items-center gap-2">
        <LightbulbIcon className="text-icon-normal-normal size-6" aria-hidden="true" />
        <span className="text-heading-medium text-text-normal-normal">Agent Studio</span>
      </div>
      <Button variant="icon-only-gray" size="md" aria-label="Agent Studio 더보기">
        <KebabIcon className="size-6" aria-hidden="true" />
      </Button>
    </header>
  );
}
