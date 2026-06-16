import ArrowRightIcon from '@/public/icons/icon/arrow_right2.svg';
import BorderColorIcon from '@/public/icons/icon/edit_pencil.svg';
import KebabIcon from '@/public/icons/icon/kebeb 2.svg';
import { Button } from '@/shared/components/ui/button';

import { AGENT_STUDIO_SETTINGS_FIXTURE } from '../../fixtures/agentStudioFixtures';

export default function AgentEditorLeftPane() {
  return (
    <aside className="border-line-normal-neutral flex w-105 shrink-0 flex-col items-start border-r">
      <header className="border-line-normal-neutral sticky top-0 flex h-13 w-full items-center border-b px-6 py-2">
        <div className="flex min-w-0 flex-1 items-center overflow-hidden">
          <Button variant="text-secondary-mono" size="sm" className="rounded-lg px-2 py-1">
            Agent Studio
          </Button>
          <ArrowRightIcon className="text-icon-normal-assistive size-5 shrink-0" aria-hidden="true" />
          <span className="text-heading-small text-text-normal-normal max-w-50 truncate px-2 py-1">
            {AGENT_STUDIO_SETTINGS_FIXTURE.title}
          </span>
        </div>
        <Button variant="icon-only-gray" size="md" aria-label="좌측 더보기">
          <KebabIcon className="size-6" aria-hidden="true" />
        </Button>
      </header>

      <div className="border-line-normal-neutral relative h-37.5 w-full shrink-0 overflow-hidden border-b bg-[linear-gradient(180deg,#002966_40.33%,#a2d5db_95.53%,#bee9d4_110.33%)]">
        <div className="absolute top-16.25 -left-10 size-53.25 rounded-full bg-[#c2ebd9]" />
        <div className="absolute top-16.25 left-61.5 size-53.25 rounded-full bg-[#c2ebd9]" />
        <div className="absolute top-5.75 left-1/2 flex h-43.25 w-44.75 -translate-x-1/2 flex-col gap-3 overflow-hidden rounded-[9px] py-3 shadow-[0_0_4px_rgba(105,165,255,0.12)] [background-image:linear-gradient(184.82deg,rgba(255,255,255,0.7)_5.08%,rgba(255,255,255,0)_14.61%,rgba(255,255,255,0.02)_41.95%,rgba(255,255,255,0.194)_57.43%,rgba(255,255,255,0.8)_69.9%,#fff_83.79%)]">
          <div className="flex w-full flex-col gap-1.5 px-3">
            <div className="h-2.25 w-10.75 rounded-full bg-[linear-gradient(90deg,#c9defe_0%,#9ec5ff_100%)]" />
            <div className="flex h-2.25 items-center gap-0.75">
              <div className="h-2.25 w-4 rounded-full bg-[linear-gradient(90deg,#c9defe_0%,#9ec5ff_100%)]" />
              <div className="h-2.25 w-7.5 rounded-full bg-[linear-gradient(90deg,#c9defe_0%,#9ec5ff_100%)]" />
            </div>
            <div className="h-2.25 w-33.25 rounded-full bg-[linear-gradient(90deg,#c9defe_0%,#9ec5ff_100%)]" />
            <div className="h-2.5 w-17 rounded-full bg-[linear-gradient(90deg,#c9defe_0%,#9ec5ff_100%)]" />
          </div>
          <div className="border-static-white flex w-full flex-col border-t pt-3 px-3">
            <div className="bg-accent-light-blue-lighten flex h-6.75 w-full items-center justify-center gap-1 overflow-hidden rounded-full px-1 py-1.5">
              <span className="flex size-4.5 shrink-0 items-center justify-center rounded-full p-0.5">
                <BorderColorIcon className="text-icon-primary-normal size-3" aria-hidden="true" />
              </span>
              <span className="bg-fill-primary-normal-neutral h-2.25 min-w-0 flex-1 rounded-full" />
              <span className="size-4.5 shrink-0 rounded-full bg-[linear-gradient(270deg,rgba(158,197,255,0.68)_0%,rgba(26,117,255,0.68)_100%)]" />
            </div>
          </div>
        </div>
      </div>

      <div className="flex w-full flex-col items-start gap-4 px-8 py-6">
        <h1 className="text-heading-xlarge text-text-normal-strong w-full truncate">
          {AGENT_STUDIO_SETTINGS_FIXTURE.title}
        </h1>
        <div className="text-body-small text-text-normal-alternative flex w-full flex-col">
          {AGENT_STUDIO_SETTINGS_FIXTURE.descriptionLines.map((line) => (
            <p key={line}>{line}</p>
          ))}
        </div>
      </div>
    </aside>
  );
}
