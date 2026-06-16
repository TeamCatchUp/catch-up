import DefaultProfileIcon from '@/public/icons/icon/default_profile.svg';
import SparkleIcon from '@/public/icons/icon/sparkle.svg';
import { Button } from '@/shared/components/ui/button';

import type { AgentStudioCardModel } from '../../types/agentStudioModel';

interface AgentCardProps {
  agent: AgentStudioCardModel;
}

export default function AgentCard({ agent }: AgentCardProps) {
  return (
    <article className="bg-fill-primary-normal-assistive flex h-70.75 min-w-80 flex-1 flex-col items-start gap-3 rounded-xl p-3">
      <span className="bg-fill-primary-normal-neutral text-heading-small text-text-primary-normal w-fit rounded-lg px-2.5 py-1">
        운영중
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
        <div className="flex w-full items-center justify-between">
          <Button variant="text-secondary-mono" size="sm" aria-label={`${agent.title} 사용 안함`}>
            사용 안함
          </Button>
          <Button
            variant="capsule-solid-primary"
            size="sm"
            className="bg-[radial-gradient(circle_at_50%_3%,#030303_0%,#090711_32.36%,#0e0a1e_64.72%,#1c133f_66.03%,#2e1f6d_71.55%,#411a9a_77.07%,#2d50cd_84.07%,#1a75ff_91.07%,#2d81ff_93.3%,#418dff_95.53%,#69a5ff_100%)]"
          >
            <SparkleIcon className="text-static-white size-5" aria-hidden="true" />
            사용하기
          </Button>
        </div>
      </div>
    </article>
  );
}
