'use client';

// 하이브리드 검색 결과 카드 (RAG 출처 카드 스타일).
// source가 'unknown'인 경우 제네릭 file 아이콘 + "기타" 라벨로 fallback.

import FileIcon from '@/public/icons/icon/file.svg';
import OpenInNew from '@/public/icons/icon/open_in_new.svg';
import ChannelTalk from '@/public/icons/logo/ChannelTalk.svg';
import Confluence from '@/public/icons/logo/Confluence.svg';
import GitHub from '@/public/icons/logo/GitHub.svg';
import Jira from '@/public/icons/logo/Jira.svg';
import Slack from '@/public/icons/logo/Slack.svg';

import type { CardSourceType } from '../utils/mapHybridSearchResult';

interface HybridSearchResultCardProps {
  sourceType: CardSourceType;
  integrationLabel: string;
  contextLabel: string;
  title: string;
  url: string;
  author: string;
  changedAt: string;
  identifier?: string;
}

const SOURCE_LOGO: Record<CardSourceType, React.FC<React.SVGProps<SVGSVGElement>>> = {
  confluence: Confluence,
  jira: Jira,
  slack: Slack,
  github: GitHub,
  channel_talk: ChannelTalk,
  unknown: FileIcon,
};

// 보안: javascript:, data: 등 위험 스킴 차단. http/https만 허용.
const ALLOWED_URL_SCHEMES = ['http:', 'https:'] as const;

function isSafeUrl(raw: string): boolean {
  if (!raw) return false;
  try {
    const parsed = new URL(raw);
    return (ALLOWED_URL_SCHEMES as readonly string[]).includes(parsed.protocol);
  } catch {
    return false;
  }
}

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
  const canOpen = isSafeUrl(url);

  const handleClick = () => {
    if (!canOpen) return;
    window.open(url, '_blank', 'noopener,noreferrer');
  };

  return (
    <button
      type="button"
      onClick={handleClick}
      disabled={!canOpen}
      className="flex w-full flex-col items-start gap-2.5 rounded-xl py-2 text-left enabled:cursor-pointer disabled:cursor-default"
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
