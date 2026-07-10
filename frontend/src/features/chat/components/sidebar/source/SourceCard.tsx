import type { ChatSource } from '@/features/chat/types';
import Book from '@/public/icons/icon/book.svg';
import Check from '@/public/icons/icon/check.svg';
import OpenInNew from '@/public/icons/icon/open_in_new.svg';
import Tag from '@/public/icons/icon/tag.svg';
import ChannelTalk from '@/public/icons/logo/ChannelTalk.svg';
import Confluence from '@/public/icons/logo/Confluence.svg';
import Github from '@/public/icons/logo/GitHub.svg';
import Jira from '@/public/icons/logo/Jira.svg';
import Slack from '@/public/icons/logo/Slack.svg';

interface Props {
  source: ChatSource;
  /** 인용된 출처 섹션에서만 true */
  showCount?: boolean;
  count?: number;
}

const INTEGRATION_LABEL: Record<ChatSource['source_type'], string> = {
  slack: 'Slack',
  github: 'Github',
  jira: 'Jira',
  confluence: 'Confluence',
  channel_talk: '채널톡',
  unknown: '',
};

/** {source_type}.{entity_type} 조합별 라벨 suffix. 매핑 누락 시 base 라벨만 표시. */
const ENTITY_LABEL_SUFFIX: Partial<Record<`${ChatSource['source_type']}.${ChatSource['entity_type']}`, string>> = {
  'channel_talk.document_article': '도큐먼트',
  'channel_talk.user_chat': '문의',
};

const getIntegrationLabel = (source: ChatSource) => {
  const base = INTEGRATION_LABEL[source.source_type];
  const suffix = ENTITY_LABEL_SUFFIX[`${source.source_type}.${source.entity_type}`];
  return suffix ? `${base} - ${suffix}` : base;
};

const renderSourceLogo = (sourceType: ChatSource['source_type']) => {
  if (sourceType === 'jira') return <Jira className="h-5 w-5 shrink-0" />;
  if (sourceType === 'slack') return <Slack className="h-5 w-5 shrink-0" />;
  if (sourceType === 'confluence') return <Confluence className="h-5 w-5 shrink-0" />;
  if (sourceType === 'github') return <Github className="h-5 w-5 shrink-0" />;
  if (sourceType === 'channel_talk') return <ChannelTalk className="h-4 w-4 shrink-0" />;
  return null;
};

export default function SourceCard({ source, showCount = true, count }: Props) {
  const handleClick = () => {
    if (!source.html_url) return;
    window.open(source.html_url, '_blank', 'noopener,noreferrer');
  };

  const isSlack = source.source_type === 'slack';
  const isChannelTalkArticle = source.source_type === 'channel_talk' && source.entity_type === 'document_article';
  const integrationLabel = getIntegrationLabel(source);

  const repoText = source.repo?.trim() ? source.repo : '-';
  const titleText = source.title?.trim() ? source.title : '-';
  // Slack은 메시지 원문 느낌으로 따옴표 wrap
  const displayTitle = isSlack && source.title?.trim() ? `"${titleText}"` : titleText;
  const dateText = source.date?.trim() ? source.date : '-';
  const authorText = source.author?.trim() ? source.author : '-';

  return (
    <button
      type="button"
      onClick={handleClick}
      className="flex w-full cursor-pointer flex-col items-start gap-2.5 text-left"
    >
      <div className="flex w-full items-center gap-2.5">
        <div className="bg-fill-normal-strong border-line-normal-assistive flex h-7 min-w-6.5 items-center justify-center gap-1 rounded-full border px-1.5 py-1">
          {renderSourceLogo(source.source_type)}
          {showCount && (
            <span className="text-body-xsmall text-text-normal-strong whitespace-nowrap">{count ?? 0}</span>
          )}
        </div>
        <span className="text-label-xsmall text-text-normal-alternative truncate">{integrationLabel}</span>
        <span
          aria-hidden="true"
          className="bg-fill-normal-strong border-line-normal-neutral flex size-6.5 shrink-0 items-center justify-center rounded-lg border p-0.5"
        >
          <OpenInNew className="text-icon-normal-neutral size-4.5" />
        </span>
      </div>

      <div className="flex w-full items-center gap-2">
        <span className="bg-fill-normal-normal border-line-normal-normal rounded-md2 flex size-5 shrink-0 items-center border-2 p-0.5">
          {isChannelTalkArticle ? (
            <Book className="text-icon-normal-neutral size-4" />
          ) : (
            <Tag className="text-icon-normal-neutral size-4" />
          )}
        </span>
        <span className="text-body-xsmall text-text-normal-alternative min-w-0 flex-1 truncate">{repoText}</span>
      </div>

      <div className="text-body-small text-text-normal-normal line-clamp-2 w-full break-keep wrap-break-word">
        {displayTitle}
      </div>

      <div className="text-body-xsmall text-text-normal-assistive flex w-full items-center gap-1.5">
        <span className="whitespace-nowrap">{authorText}</span>
        <span className="bg-dim-black-10 size-1 shrink-0 rounded-full" />
        <span className="whitespace-nowrap">{dateText}</span>
        {source.issue_key ? (
          <>
            <span className="bg-dim-black-10 size-1 shrink-0 rounded-full" />
            <span className="whitespace-nowrap">[{source.issue_key}]</span>
          </>
        ) : source.github_number !== undefined ? (
          <>
            <span className="bg-dim-black-10 size-1 shrink-0 rounded-full" />
            <span className="whitespace-nowrap">#{source.github_number}</span>
          </>
        ) : null}
        {isChannelTalkArticle && (
          <>
            <span className="bg-dim-black-10 size-1 shrink-0 rounded-full" />
            <span className="flex items-center gap-1 whitespace-nowrap">
              발행 완료
              <Check className="text-icon-primary-assistive size-4.5" />
            </span>
          </>
        )}
      </div>
    </button>
  );
}
