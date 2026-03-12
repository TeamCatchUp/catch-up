import type { ChatSource } from '@/features/chat/types';
import LightbulbFilled from '@/public/icons/icon/lightbulb_filled.svg';
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

// 이 출처가 사용된 이유(content) 미리보기 최대 글자 수
const REASON_PREVIEW_MAX_LENGTH = 120;

const SourceCard = ({ source, showCount = true, count }: Props) => {
  // html_url이 없으면 클릭 무시
  const handleClick = () => {
    if (!source.html_url) return;
    window.open(source.html_url, '_blank', 'noopener,noreferrer');
  };

  // source_type을 로고 렌더링용 카테고리로 변환
  const getSourceLogoType = (): SourceLogoType => {
    if (source.source_type === 'jira') return 'jira';
    if (source.source_type === 'slack') return 'slack';
    if (source.source_type === 'confluence') return 'confluence';
    return 'github'; // code | pr | github_issue
  };

  const renderSourceLogo = () => {
    const sourceLogoType = getSourceLogoType();
    if (sourceLogoType === 'jira') return <Jira className="h-4 w-4 shrink-0" />;
    if (sourceLogoType === 'slack') return <Slack className="h-4 w-4 shrink-0" />;
    if (sourceLogoType === 'confluence') return <Confluence className="h-4 w-4 shrink-0" />;
    return <Github className="h-4 w-4 shrink-0" />;
  };

  // 각 필드 빈값 fallback 처리
  const repoText = source.repo?.trim() ? source.repo : '-';
  const titleText = source.title?.trim() ? source.title : '-';
  const reasonText = source.content?.trim() ? source.content : '-';

  // content가 길면 120자까지 자르고 "...더보기" 표시
  const reasonPreview =
    reasonText.length > REASON_PREVIEW_MAX_LENGTH
      ? reasonText.slice(0, REASON_PREVIEW_MAX_LENGTH).trimEnd()
      : reasonText;
  const isReasonTrimmed = reasonText.length > REASON_PREVIEW_MAX_LENGTH;

  const dateText = source.date?.trim() ? source.date : '-';
  const authorText = source.author?.trim() ? source.author : '-';

  return (
    <button
      type="button"
      onClick={handleClick}
      className="flex w-full cursor-pointer flex-col gap-2.5 rounded-xl bg-fill-normal px-1 py-2.5 text-left"
    >
      {/* 헤더: 플랫폼 로고 + 인용 횟수 + 저장소명 */}
      <div className="flex h-6 items-center gap-1.5">
        <div className="bg-fill-interaction-hover flex h-6 min-w-6.5 items-center justify-center gap-1 rounded-full px-1.5 py-0.5">
          {renderSourceLogo()}
          {showCount && <span className="text-body-xsmall text-content-neutral whitespace-nowrap">{count ?? 0}</span>}
        </div>
        <div className="min-w-0 flex-1">
          <div className="text-body-xsmall truncate text-content-alternative hover:underline">{repoText}</div>
        </div>
      </div>

      {/* 문서 제목 (최대 2줄) */}
      <div className="text-heading-small text-content-normal line-clamp-2 wrap-break-word hover:underline">{titleText}</div>

      {/* 이 출처가 사용된 이유 (content 필드, 최대 2줄 + 120자 truncate) */}
      <div className="border-edge-neutral flex w-full flex-col gap-0.5 border-l-2 py-0.5 pl-3">
        {source.is_cited && (
          <div className="flex items-center gap-1">
            <LightbulbFilled className="text-content-assistive h-4 w-4" />
            <span className="text-body-xsmall whitespace-nowrap text-content-alternative">이 출처가 사용된 이유</span>
          </div>
        )}
        <div className="text-body-small line-clamp-2 wrap-break-word text-content-alternative">
          {reasonPreview}
          {isReasonTrimmed && <span className="text-content-assistive"> ...더보기</span>}
        </div>
      </div>

      {/* 메타데이터: 날짜 | 작성자 */}
      <div className="text-body-xsmall text-content-assistive flex items-center gap-2">
        <span className="shrink-0">{dateText}</span>
        <div className="bg-edge-neutral h-3.75 w-px" />
        <span className="shrink-0">{authorText}</span>
      </div>
    </button>
  );
};

export default SourceCard;
