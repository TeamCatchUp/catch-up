import DefaultProfileIcon from '@/public/icons/icon/default_profile.svg';
import KebabIcon from '@/public/icons/icon/kebab.svg';
import { Button } from '@/shared/components/ui/button';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/shared/components/ui/dropdown-menu';
import { isSafeUrl } from '@/shared/utils/isSafeUrl';

import type { AgentStudioCardModel } from '../../types/agentStudioModel';

interface AgentCardProps {
  agent: AgentStudioCardModel;
  onActivate?: (agent: AgentStudioCardModel) => void;
  onDeactivate?: (agent: AgentStudioCardModel) => void;
  actionDisabled?: boolean;
  layout?: 'grouped' | 'flat';
}

export default function AgentCard({
  agent,
  onActivate,
  onDeactivate,
  actionDisabled = false,
  layout = 'grouped',
}: AgentCardProps) {
  const isInactive = agent.status === 'inactive';
  const safeAuthorProfileImageUrl =
    agent.authorProfileImageUrl && isSafeUrl(agent.authorProfileImageUrl) ? agent.authorProfileImageUrl : null;
  const containerClassName =
    layout === 'flat'
      ? 'border-line-normal-normal bg-fill-normal-assistive-dark flex min-w-80 flex-none basis-[calc((100%_-_48px)/3)] flex-col overflow-hidden rounded-xl border p-5'
      : 'border-line-normal-normal bg-fill-normal-assistive-dark flex w-full flex-col overflow-hidden rounded-xl border p-5';

  const metadataRow = (
    <div className="text-body-xsmall text-text-normal-alternative flex h-6 shrink-0 items-center gap-2">
      <div className="flex shrink-0 items-center gap-1.5">
        <div className="border-fill-normal-strong flex size-5 shrink-0 items-center justify-center overflow-hidden rounded-full border">
          {safeAuthorProfileImageUrl ? (
            // eslint-disable-next-line @next/next/no-img-element
            <img src={safeAuthorProfileImageUrl} alt="" className="size-full object-cover" />
          ) : (
            <DefaultProfileIcon className="size-full" aria-hidden="true" />
          )}
        </div>
        <span className="max-w-24 truncate">{agent.authorName}</span>
      </div>
      <span className="bg-dim-black-10 size-1 shrink-0 rounded-full" aria-hidden="true" />
      <span className="shrink-0">수정일</span>
      <span className="truncate">{agent.updatedAtLabel}</span>
    </div>
  );

  if (isInactive) {
    return (
      <article className={containerClassName}>
        <div
          className={
            layout === 'flat'
              ? 'flex min-h-0 w-full flex-1 flex-col gap-3 overflow-hidden'
              : 'flex w-full flex-col gap-3'
          }
        >
          <h3 className="text-heading-medium text-text-normal-normal w-full shrink-0 truncate">{agent.title}</h3>
          <p className="text-body-small text-text-normal-alternative line-clamp-2 w-full shrink-0">
            {agent.description}
          </p>
          {metadataRow}
        </div>
        <Button
          variant="capsule-outline-mono"
          size="sm"
          className="text-text-normal-normal mt-4 h-9 w-full"
          disabled={actionDisabled}
          onClick={() => onActivate?.(agent)}
        >
          다시 운영하기
        </Button>
      </article>
    );
  }

  return (
    <article className={containerClassName}>
      <div
        className={
          layout === 'flat' ? 'flex min-h-0 w-full flex-1 flex-col gap-9 overflow-hidden' : 'flex w-full flex-col gap-9'
        }
      >
        <div className="flex w-full flex-col gap-3">
          <div className="flex w-full items-center gap-3">
            <h3 className="text-heading-medium text-text-normal-normal min-w-0 flex-1 truncate">{agent.title}</h3>
            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <Button
                  variant="icon-only-gray"
                  size="md"
                  aria-label={`${agent.title} 카드 메뉴`}
                  disabled={actionDisabled}
                >
                  <KebabIcon className="size-6" aria-hidden="true" />
                </Button>
              </DropdownMenuTrigger>
              <DropdownMenuContent align="end" sideOffset={4} className="min-w-24">
                <DropdownMenuItem disabled={actionDisabled} onSelect={() => onDeactivate?.(agent)}>
                  사용 안함
                </DropdownMenuItem>
              </DropdownMenuContent>
            </DropdownMenu>
          </div>
          <p className="text-body-small text-text-normal-alternative line-clamp-2 w-full shrink-0">
            {agent.description}
          </p>
        </div>
        {metadataRow}
      </div>
    </article>
  );
}
