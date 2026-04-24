import type { ChatSource } from '@/features/chat/types';
import OpenInNew from '@/public/icons/icon/open_in_new.svg';
import Tag from '@/public/icons/icon/tag.svg';
import Confluence from '@/public/icons/logo/Confluence.svg';
import Github from '@/public/icons/logo/GitHub.svg';
import Jira from '@/public/icons/logo/Jira.svg';
import Slack from '@/public/icons/logo/Slack.svg';

interface Props {
  source: ChatSource;
  /** 인용 횟수 배지 표시 여부 (인용된 출처 섹션에서만 true) */
  showCount?: boolean;
  /** 답변에서 해당 출처가 인용된 횟수 */
  count?: number;
}

// source_type을 플랫폼 로고 카테고리로 매핑하기 위한 타입
// code | pr | github_issue → 'github'로 통합
type SourceLogoType = 'jira' | 'github' | 'slack' | 'confluence';

const INTEGRATION_LABEL: Record<SourceLogoType, string> = {
  slack: 'Slack',
  github: 'Github',
  jira: 'Jira',
  confluence: 'Confluence',
};

const getSourceLogoType = (sourceType: ChatSource['source_type']): SourceLogoType => {
  if (sourceType === 'jira') return 'jira';
  if (sourceType === 'slack') return 'slack';
  if (sourceType === 'confluence') return 'confluence';
  return 'github'; // code | pr | github_issue
};

const renderSourceLogo = (logoType: SourceLogoType) => {
  if (logoType === 'jira') return <Jira className="h-5 w-5 shrink-0" />;
  if (logoType === 'slack') return <Slack className="h-5 w-5 shrink-0" />;
  if (logoType === 'confluence') return <Confluence className="h-5 w-5 shrink-0" />;
  return <Github className="h-5 w-5 shrink-0" />;
};

export default function SourceCard({ source, showCount = true, count }: Props) {
  // html_url이 없으면 클릭 무시
  const handleClick = () => {
    if (!source.html_url) return;
    window.open(source.html_url, '_blank', 'noopener,noreferrer');
  };

  const logoType = getSourceLogoType(source.source_type);
  const integrationLabel = INTEGRATION_LABEL[logoType];
  const isSlack = logoType === 'slack';

  // 각 필드 빈값 fallback 처리
  const repoText = source.repo?.trim() ? source.repo : '-';
  const titleText = source.title?.trim() ? source.title : '-';
  // Slack 카드는 title을 따옴표로 감싸 메시지 원문처럼 표현
  const displayTitle = isSlack && source.title?.trim() ? `"${titleText}"` : titleText;
  const dateText = source.date?.trim() ? source.date : '-';
  const authorText = source.author?.trim() ? source.author : '-';

  return (
    <button
      type="button"
      onClick={handleClick}
      className="flex w-full cursor-pointer flex-col items-start gap-2.5 text-left"
    >
      {/* Row 1: 플랫폼 로고+카운트 배지 + 통합 이름 + 원문 열기 버튼 */}
      <div className="flex w-full items-center gap-2.5">
        <div className="bg-fill-strong border-edge-assistive flex h-7 min-w-6.5 items-center justify-center gap-1 rounded-full border px-1.5 py-1">
          {renderSourceLogo(logoType)}
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

      {/* Row 2: 태그 아이콘 + 채널/워크스페이스/저장소명 */}
      <div className="flex w-full items-center gap-2">
        <span className="bg-fill-normal border-edge-normal rounded-md2 flex shrink-0 items-center border p-0.5">
          <Tag className="text-icon-neutral size-4" />
        </span>
        <span className="text-body-xsmall text-content-alternative min-w-0 flex-1 truncate">{repoText}</span>
      </div>

      {/* Row 3: Title (Slack은 따옴표로 감싼 메시지 원문) */}
      <div className="text-body-small text-content-normal line-clamp-2 w-full wrap-break-word">{displayTitle}</div>

      {/* Row 4: 메타 — 작성자 · 날짜 (Slack 참여자 수 / 이슈키는 Spec 5에서 데이터 확장 후 추가) */}
      <div className="text-body-xsmall text-content-assistive flex w-full items-center gap-1.5">
        <span className="whitespace-nowrap">{authorText}</span>
        <span className="bg-dim-black-10 size-1 shrink-0 rounded-full" />
        <span className="whitespace-nowrap">{dateText}</span>
      </div>
    </button>
  );
}
