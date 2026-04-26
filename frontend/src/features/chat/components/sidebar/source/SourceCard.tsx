import type { ChatSource } from '@/features/chat/types';
import OpenInNew from '@/public/icons/icon/open_in_new.svg';
import Tag from '@/public/icons/icon/tag.svg';
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
  unknown: '',
};

const renderSourceLogo = (sourceType: ChatSource['source_type']) => {
  if (sourceType === 'jira') return <Jira className="h-5 w-5 shrink-0" />;
  if (sourceType === 'slack') return <Slack className="h-5 w-5 shrink-0" />;
  if (sourceType === 'confluence') return <Confluence className="h-5 w-5 shrink-0" />;
  if (sourceType === 'github') return <Github className="h-5 w-5 shrink-0" />;
  return null;
};

export default function SourceCard({ source, showCount = true, count }: Props) {
  const handleClick = () => {
    if (!source.html_url) return;
    window.open(source.html_url, '_blank', 'noopener,noreferrer');
  };

  const isSlack = source.source_type === 'slack';
  const integrationLabel = INTEGRATION_LABEL[source.source_type];

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
      {/* Row 1: 로고+카운트 pill · integration 이름 · open_in_new 버튼 */}
      <div className="flex w-full items-center gap-2.5">
        <div className="bg-fill-strong border-edge-assistive flex h-7 min-w-6.5 items-center justify-center gap-1 rounded-full border px-1.5 py-1">
          {renderSourceLogo(source.source_type)}
          {showCount && <span className="text-body-xsmall text-content-strong whitespace-nowrap">{count ?? 0}</span>}
        </div>
        <span className="text-label-xsmall text-content-alternative truncate">{integrationLabel}</span>
        <span
          aria-hidden="true"
          className="bg-fill-strong border-edge-neutral flex size-6.5 shrink-0 items-center justify-center rounded-lg border p-0.5"
        >
          <OpenInNew className="text-icon-neutral size-4.5" />
        </span>
      </div>

      {/* Row 2: tag pill · 채널/워크스페이스/repo */}
      <div className="flex w-full items-center gap-2">
        <span className="bg-fill-normal border-edge-normal rounded-md2 flex size-5 shrink-0 items-center border-2 p-0.5">
          <Tag className="text-icon-neutral size-4" />
        </span>
        <span className="text-body-xsmall text-content-alternative min-w-0 flex-1 truncate">{repoText}</span>
      </div>

      {/* Row 3: Title */}
      <div className="text-body-small text-content-normal line-clamp-2 w-full wrap-break-word">{displayTitle}</div>

      {/* Row 4: 작성자 · 날짜 · [이슈키] / #번호 (jira/github only) */}
      <div className="text-body-xsmall text-content-assistive flex w-full items-center gap-1.5">
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
      </div>
    </button>
  );
}
