import DefaultProfileIcon from '@/public/icons/icon/default_profile.svg';
import SparkleIcon from '@/public/icons/icon/sparkle.svg';
import { Button } from '@/shared/components/ui/button';
import { cn } from '@/shared/utils/cn';

import type { AgentStudioCardModel, AgentStudioStatus } from '../../types/agentStudioModel';

interface AgentCardProps {
  agent: AgentStudioCardModel;
  onActivate?: (agent: AgentStudioCardModel) => void;
  onDeactivate?: (agent: AgentStudioCardModel) => void;
  actionDisabled?: boolean;
}

const AGENT_STUDIO_USE_BUTTON_GRADIENT =
  'radial-gradient(circle at 50% 3%, #030303 0%, #090711 32.36%, #0e0a1e 64.72%, #1c133f 66.03%, #2e1f6d 71.55%, #411a9a 77.07%, #2d50cd 84.07%, #1a75ff 91.07%, #2d81ff 93.3%, #418dff 95.53%, #69a5ff 100%)';

const STATUS_STYLE: Record<
  AgentStudioStatus,
  {
    label: string;
    outerClassName: string;
    labelClassName: string;
  }
> = {
  active: {
    label: '운영중',
    outerClassName: 'bg-fill-primary-normal-assistive',
    labelClassName: 'bg-fill-primary-normal-neutral text-text-primary-normal',
  },
  draft: {
    label: '제작중',
    outerClassName: 'bg-fill-normal-strong',
    labelClassName: 'bg-fill-normal-interaction-disable text-text-normal-alternative',
  },
  inactive: {
    label: '사용 안함',
    outerClassName: 'bg-fill-normal-strong',
    labelClassName: 'bg-fill-normal-interaction-disable text-text-normal-alternative',
  },
};

export default function AgentCard({ agent, onActivate, onDeactivate, actionDisabled = false }: AgentCardProps) {
  const statusStyle = STATUS_STYLE[agent.status];
  const isInactive = agent.status === 'inactive';

  return (
    <article
      className={cn(
        'flex h-70.75 min-w-80 flex-1 flex-col items-start gap-3 rounded-xl p-3',
        statusStyle.outerClassName,
      )}
    >
      <span className={cn('text-heading-small w-fit rounded-lg px-2.5 py-1', statusStyle.labelClassName)}>
        {statusStyle.label}
      </span>
      <div className="border-line-normal-normal bg-fill-normal-assistive-dark flex w-full flex-1 flex-col items-end justify-between gap-4 overflow-hidden rounded-xl border p-5">
        <div className="flex min-h-0 w-full flex-1 flex-col items-start gap-3 overflow-hidden">
          <h3 className="text-heading-medium text-text-normal-normal w-full shrink-0 truncate">{agent.title}</h3>
          <p className="text-body-small text-text-normal-alternative line-clamp-2 w-full shrink-0">
            {agent.description}
          </p>
          <div className="text-body-xsmall text-text-normal-alternative flex h-6 shrink-0 items-center gap-2">
            <div className="border-fill-normal-strong flex size-5 shrink-0 items-center justify-center overflow-hidden rounded-full border">
              <DefaultProfileIcon className="size-full" aria-hidden="true" />
            </div>
            <span className="truncate">{agent.authorName}</span>
            <span className="bg-dim-alpha-black10 size-1 shrink-0 rounded-full" aria-hidden="true" />
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
              style={{ background: AGENT_STUDIO_USE_BUTTON_GRADIENT }}
            >
              <SparkleIcon className="size-5" aria-hidden="true" />
              사용하기
            </Button>
          </div>
        )}
      </div>
    </article>
  );
}
