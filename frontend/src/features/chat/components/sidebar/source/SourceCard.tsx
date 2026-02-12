import LightbulbFilled from '/public/icons/icon/lightbulb_filled.svg';
import Github from '/public/icons/logo/GitHub.svg';
import Jira from '/public/icons/logo/Jira.svg';
import Slack from '/public/icons/logo/Slack.svg';

interface Props {
  source: ChatSource;
  showCount?: boolean;
  count?: number;
}

type SourceLogoType = 'jira' | 'github' | 'slack';

const REASON_PREVIEW_MAX_LENGTH = 120;

const SourceCard = ({ source, showCount = true, count }: Props) => {
  const handleClick = () => {
    if (!source.html_url) {
      return;
    }

    window.open(source.html_url, '_blank', 'noopener,noreferrer');
  };

  const getSourceLogoType = (): SourceLogoType => {
    if (source.source_type === 'jira') {
      return 'jira';
    }

    // Backend type에 slack이 아직 없어도 source 정보에 slack이 들어오면 로고를 맞춰서 렌더링한다.
    const lowerRepo = source.repo?.toLowerCase() ?? '';
    const lowerTitle = source.title?.toLowerCase() ?? '';
    if (lowerRepo.includes('slack') || lowerTitle.includes('slack')) {
      return 'slack';
    }

    return 'github';
  };

  const renderSourceLogo = () => {
    const sourceLogoType = getSourceLogoType();

    if (sourceLogoType === 'jira') {
      return <Jira className="h-4 w-4 shrink-0" />;
    }

    if (sourceLogoType === 'slack') {
      return <Slack className="h-4 w-4 shrink-0" />;
    }

    return <Github className="h-4 w-4 shrink-0" />;
  };

  const repoText = source.repo?.trim() ? source.repo : '-';
  const titleText = source.title?.trim() ? source.title : '-';
  const reasonText = source.content?.trim() ? source.content : '-';
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
      className="flex w-full cursor-pointer flex-col gap-2.5 rounded-xl bg-white px-1 py-2.5 text-left"
    >
      <div className="flex h-6 items-center gap-1.5">
        <div className="bg-neutral-2 flex h-6 min-w-6.5 items-center justify-center gap-1 rounded-full px-1.5 py-0.5">
          {renderSourceLogo()}
          {showCount && (
            <span className="text-body-xsmall text-gray-70 whitespace-nowrap">
              {count ?? 0}
            </span>
          )}
        </div>
        <div className="min-w-0 flex-1">
          <div className="text-body-xsmall truncate text-gray-50 hover:underline">
            {repoText}
          </div>
        </div>
      </div>

      <div className="text-heading-small text-gray-80 line-clamp-2 wrap-break-word hover:underline">
        {titleText}
      </div>

      <div className="border-neutral-3 flex w-full flex-col gap-0.5 border-l-2 py-0.5 pl-3">
        <div className="flex items-center gap-1">
          <LightbulbFilled className="h-4 w-4 text-gray-20" />
          <span className="text-body-xsmall text-gray-50 whitespace-nowrap">
            이 출처가 사용된 이유
          </span>
        </div>
        <div className="text-body-small text-gray-50 line-clamp-2 wrap-break-word">
          {reasonPreview}
          {isReasonTrimmed && <span className="text-gray-30"> ...더보기</span>}
        </div>
      </div>

      <div className="text-body-xsmall text-gray-30 flex items-center gap-2">
        <span className="shrink-0">{dateText}</span>
        <div className="bg-neutral-3 h-3.75 w-px" />
        <span className="shrink-0">{authorText}</span>
      </div>
    </button>
  );
};

export default SourceCard;
