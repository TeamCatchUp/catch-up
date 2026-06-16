import ArrowRightIcon from '@/public/icons/icon/arrow_right2.svg';
import KebabIcon from '@/public/icons/icon/kebab.svg';
import AgentEditorPreviewIllustration from '@/public/image/agent-studio/agent-editor-preview.svg';
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

      <div className="border-line-normal-neutral h-37.5 w-full shrink-0 overflow-hidden border-b">
        <AgentEditorPreviewIllustration className="size-full" aria-hidden="true" focusable="false" />
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
