import DefaultProfileIcon from '@/public/icons/icon/default_profile.svg';
import SparkleIcon from '@/public/icons/icon/sparkle.svg';
import { Button } from '@/shared/components/ui/button';
import { isSafeUrl } from '@/shared/utils/isSafeUrl';

import type { AgentStudioCardModel } from '../../types/agentStudioModel';

interface AgentCardProps {
  agent: AgentStudioCardModel;
  onActivate?: (agent: AgentStudioCardModel) => void;
  onDeactivate?: (agent: AgentStudioCardModel) => void;
  actionDisabled?: boolean;
  layout?: 'grouped' | 'flat';
}

const AGENT_STUDIO_USE_BUTTON_GRADIENT =
  'radial-gradient(circle at 50% 2.78%, #030303 0%, #090711 32.36%, #0e0a1e 64.721%, #1c133f 66.029%, #2e1f6d 71.547%, #412a9a 77.065%, #2d50cd 84.066%, #1a75ff 91.068%, #2d81ff 93.301%, #418dff 95.534%, #69a5ff 100%)';

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
      ? 'border-line-normal-normal bg-fill-normal-assistive-dark flex h-52.75 min-w-80 flex-none basis-[calc((100%_-_48px)/3)] flex-col items-end justify-between gap-4 overflow-hidden rounded-xl border p-5'
      : 'border-line-normal-normal bg-fill-normal-assistive-dark flex w-full flex-col items-end justify-between gap-4 overflow-hidden rounded-xl border p-5';
  const contentClassName =
    layout === 'flat'
      ? 'flex min-h-0 w-full flex-1 flex-col items-start gap-3 overflow-hidden'
      : 'flex w-full flex-col items-start gap-3';
  const content = (
    <>
      <div className={contentClassName}>
        <h3 className="text-heading-medium text-text-normal-normal w-full shrink-0 truncate">{agent.title}</h3>
        <p className="text-body-small text-text-normal-alternative line-clamp-2 w-full shrink-0">{agent.description}</p>
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
            <span className="max-w-24 overflow-hidden text-ellipsis whitespace-nowrap">{agent.authorName}</span>
          </div>
          <span
            className="size-1 shrink-0"
            style={{
              borderRadius: 'var(--radius-rounded, 1000px)',
              background: 'var(--Dim-Alpha-black10, rgba(0, 0, 0, 0.10))',
            }}
            aria-hidden="true"
          />
          <span className="shrink-0">수정일</span>
          <span className="truncate">{agent.updatedAtLabel}</span>
        </div>
      </div>
      {isInactive ? (
        <Button
          variant="capsule-outline-mono"
          size="sm"
          className="text-text-normal-normal h-9 w-full"
          disabled={actionDisabled}
          onClick={() => onActivate?.(agent)}
        >
          다시 운영하기
        </Button>
      ) : (
        <div className="flex w-full items-center justify-between">
          <Button
            variant="text-secondary-mono"
            size="sm"
            aria-label={`${agent.title} 사용 안함`}
            disabled={actionDisabled}
            onClick={() => onDeactivate?.(agent)}
          >
            사용 안함
          </Button>
          <Button
            variant="capsule-solid-primary"
            size="sm"
            className="text-static-white h-9"
            style={{ backgroundImage: AGENT_STUDIO_USE_BUTTON_GRADIENT }}
          >
            <SparkleIcon className="size-5" aria-hidden="true" />
            사용하기
          </Button>
        </div>
      )}
    </>
  );

  return <article className={containerClassName}>{content}</article>;
}
