'use client';

// 하이브리드 검색 결과 카드 (RAG 출처 카드).
// 데이터 모델은 chat의 SourceCard와 동일한 RagSourceUiModel 사용 → fallback 로직 통일.
// 클릭은 선택(onSelect)만 — 원문은 우측 패널에 로드된다 (링크 열기 동작 없음).
// hover/selected 시 카드 배경 강조.

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
  isSelected: boolean;
  onSelect: (source: RagSourceUiModel) => void;
}

const SOURCE_LOGO: Record<RagSourceTypeModel, React.ComponentType<React.SVGProps<SVGSVGElement>>> = {
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

export default function HybridSearchResultCard({
  source,
  isSelected,
  onSelect,
}: HybridSearchResultCardProps) {
  const Logo = SOURCE_LOGO[source.source_type];

  const integrationLabel = getIntegrationLabel(source);
  const isSlack = source.source_type === 'slack';
  // Slack은 메시지 원문 느낌으로 따옴표 wrap.
  const titleText = source.title?.trim() ? source.title : '-';
  const displayTitle = isSlack && source.title?.trim() ? `"${titleText}"` : titleText;
  const contextLabel = source.repo?.trim() ? source.repo : '-';
  const dateText = source.date?.trim() ? source.date : '-';
  const authorText = source.author?.trim() ? source.author : '-';

  // selected: bg-fill-strong(#F7F7F8), hover: bg-fill-interaction-hover(#EAEBEC).
  const stateClass = isSelected ? 'bg-fill-strong' : 'hover:bg-fill-interaction-hover';

  return (
    <button
      type="button"
      onClick={() => onSelect(source)}
      aria-pressed={isSelected}
      className={`flex w-full cursor-pointer flex-col items-start gap-2 rounded-xl p-4 text-left ${stateClass}`}
    >
      {/* 헤더 — [로고 + 커넥터명] / [채널·워크스페이스명 + 외부 링크 아이콘] 단일 행. */}
      <div className="flex w-full items-center gap-2.5">
        <span className="border-edge-normal bg-fill-normal flex shrink-0 items-center justify-center rounded-full border p-1.5">
          <Logo className={source.source_type === 'channel_talk' ? 'h-4 w-4' : 'h-5 w-5'} />
        </span>
        <div className="flex min-w-0 flex-1 items-center gap-2">
          <span className="text-body-xsmall text-content-alternative shrink-0">{integrationLabel}</span>
          <span aria-hidden className="text-body-medium text-icon-alternative shrink-0">
            /
          </span>
          {/* 워크스페이스명 + 외부 링크 아이콘 호버 시 워크스페이스명에 밑줄 */}
          <div className="group/name flex min-w-0 flex-1 items-center gap-2">
            <span className="text-body-xsmall text-content-alternative truncate group-hover/name:underline">
              {contextLabel}
            </span>
            <OpenInNew className="text-icon-assistive h-4.5 w-4.5 shrink-0" />
          </div>
        </div>
      </div>
      <div className="flex w-full flex-col gap-2">
        <p className="text-body-medium text-content-normal max-w-152.5 truncate">{displayTitle}</p>
        <div className="text-body-small text-content-alternative flex items-center gap-1.5">
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
