'use client';

// 하이브리드 검색 결과 카드 (RAG 출처 카드 스타일).

import OpenInNew from '@/public/icons/icon/open_in_new.svg';
import ChannelTalk from '@/public/icons/logo/ChannelTalk.svg';
import Confluence from '@/public/icons/logo/Confluence.svg';
import GitHub from '@/public/icons/logo/GitHub.svg';
import Jira from '@/public/icons/logo/Jira.svg';
import Slack from '@/public/icons/logo/Slack.svg';
import type { DocsSource } from '@/shared/types/source';

interface HybridSearchResultCardProps {
  sourceType: DocsSource;
  integrationLabel: string;
  contextLabel: string;
  title: string;
  url: string;
  author: string;
  changedAt: string;
  identifier?: string;
}

const SOURCE_LOGO: Record<DocsSource, React.FC<React.SVGProps<SVGSVGElement>>> = {
  confluence: Confluence,
  jira: Jira,
  slack: Slack,
  github: GitHub,
  channel_talk: ChannelTalk,
};

export default function HybridSearchResultCard({
  sourceType,
  integrationLabel,
  contextLabel,
  title,
  url,
  author,
  changedAt,
  identifier,
}: HybridSearchResultCardProps) {
  const Logo = SOURCE_LOGO[sourceType];

  const handleClick = () => {
    if (!url) return;
    window.open(url, '_blank', 'noopener,noreferrer');
  };

  return (
    <button
      type="button"
      onClick={handleClick}
      className="flex w-full cursor-pointer flex-col items-start gap-2.5 rounded-xl py-2 text-left"
    >
      <div className="flex w-full items-center gap-2.5">
        <span className="border-edge-normal bg-fill-normal flex shrink-0 items-center justify-center rounded-full border p-1.5">
          <Logo className="h-5 w-5" />
        </span>
        <div className="flex min-w-0 flex-1 flex-col gap-0.5">
          <div className="flex items-center gap-2">
            <span className="text-body-small text-content-neutral truncate">{integrationLabel}</span>
            <OpenInNew className="text-icon-assistive h-4.5 w-4.5 shrink-0" />
          </div>
          <span className="text-body-xsmall text-content-neutral max-w-87.5 truncate">{contextLabel}</span>
        </div>
      </div>
      <div className="flex w-full flex-col gap-2">
        <p className="text-body-medium text-content-primary max-w-152.5 truncate">{title}</p>
        <div className="text-body-xsmall text-content-alternative flex items-center gap-1.5">
          <span className="whitespace-nowrap">{author}</span>
          <span aria-hidden className="bg-dim-black-10 h-1 w-1 shrink-0 rounded-full" />
          <span className="whitespace-nowrap">{changedAt}</span>
          {identifier && (
            <>
              <span aria-hidden className="bg-dim-black-10 h-1 w-1 shrink-0 rounded-full" />
              <span className="whitespace-nowrap">{identifier}</span>
            </>
          )}
        </div>
      </div>
    </button>
  );
}
