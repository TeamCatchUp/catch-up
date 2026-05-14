'use client';

// 하이브리드 검색 결과 카드 (RAG 출처 카드).
// 데이터 모델은 chat의 SourceCard와 동일한 RagSourceUiModel 사용 → fallback 로직 통일.
// 시각은 Figma 11686:80941 — count pill, meta pill, OpenInNew 박스 없음 (chat과 시각만 다름).

import FileIcon from '@/public/icons/icon/file.svg';
import OpenInNew from '@/public/icons/icon/open_in_new.svg';
import ChannelTalk from '@/public/icons/logo/ChannelTalk.svg';
import Confluence from '@/public/icons/logo/Confluence.svg';
import GitHub from '@/public/icons/logo/GitHub.svg';
import Jira from '@/public/icons/logo/Jira.svg';
import Slack from '@/public/icons/logo/Slack.svg';
import type { RagSourceTypeModel, RagSourceUiModel } from '@/shared/types/ragSourceModel';

interface HybridSearchResultCardProps {
  source: RagSourceUiModel;
}

const SOURCE_LOGO: Record<RagSourceTypeModel, React.FC<React.SVGProps<SVGSVGElement>>> = {
  confluence: Confluence,
  jira: Jira,
  slack: Slack,
  github: GitHub,
  channel_talk: ChannelTalk,
  unknown: FileIcon,
};

const INTEGRATION_BASE_LABEL: Record<RagSourceTypeModel, string> = {
  slack: 'Slack',
  github: 'Github',
  jira: 'Jira',
  confluence: 'Confluence',
  channel_talk: '채널톡',
  unknown: '기타',
};

const ENTITY_LABEL_SUFFIX: Partial<Record<`${RagSourceTypeModel}.${string}`, string>> = {
  'channel_talk.document_article': '도큐먼트',
  'channel_talk.user_chat': '문의',
};

const getIntegrationLabel = (source: RagSourceUiModel): string => {
  const base = INTEGRATION_BASE_LABEL[source.source_type];
  const suffix = ENTITY_LABEL_SUFFIX[`${source.source_type}.${source.entity_type}`];
  return suffix ? `${base} - ${suffix}` : base;
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

export default function HybridSearchResultCard({ source }: HybridSearchResultCardProps) {
  const Logo = SOURCE_LOGO[source.source_type];
  const canOpen = isSafeUrl(source.html_url);

  const integrationLabel = getIntegrationLabel(source);
  const isSlack = source.source_type === 'slack';
  // Slack은 메시지 원문 느낌으로 따옴표 wrap.
  const titleText = source.title?.trim() ? source.title : '-';
  const displayTitle = isSlack && source.title?.trim() ? `"${titleText}"` : titleText;
  const contextLabel = source.repo?.trim() ? source.repo : '-';
  const dateText = source.date?.trim() ? source.date : '-';
  const authorText = source.author?.trim() ? source.author : '-';

  const handleClick = () => {
    if (!canOpen) return;
    window.open(source.html_url, '_blank', 'noopener,noreferrer');
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
        <p className="text-body-medium text-content-primary max-w-152.5 truncate">{displayTitle}</p>
        <div className="text-body-xsmall text-content-alternative flex items-center gap-1.5">
          <span className="whitespace-nowrap">{authorText}</span>
          <span aria-hidden className="bg-dim-black-10 h-1 w-1 shrink-0 rounded-full" />
          <span className="whitespace-nowrap">{dateText}</span>
          {source.issue_key && (
            <>
              <span aria-hidden className="bg-dim-black-10 h-1 w-1 shrink-0 rounded-full" />
              <span className="whitespace-nowrap">[{source.issue_key}]</span>
            </>
          )}
          {source.github_number !== undefined && (
            <>
              <span aria-hidden className="bg-dim-black-10 h-1 w-1 shrink-0 rounded-full" />
              <span className="whitespace-nowrap">#{source.github_number}</span>
            </>
          )}
        </div>
      </div>
    </button>
  );
}
