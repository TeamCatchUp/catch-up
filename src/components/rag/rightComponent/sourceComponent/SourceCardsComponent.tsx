// import clsx from 'clsx';
// import File from '/public/icons/icon/file.svg';
// import Wiki from '/public/icons/logo/Wiki.svg';
// import Link from '/public/icons/icon/link.svg';
import Github from '/public/icons/logo/GitHub.svg';
// import Slack from '/public/icons/logo/Slack.svg';
// import Comment from '/public/icons/icon/chat.svg';
import Jira from '/public/icons/logo/Jira.svg';

interface Props {
  source: ChatSource;
  showCount?: boolean;
  count?: number;
}

const SOURCE_ICON_MAP: Record<ChatSource['sourceType'], React.FC<any>> = {
  // file: File,
  // wiki: Wiki,
  // url: Link,
  // github: Github,
  // slack: Slack,
  // comment: Comment,
  code: Github,
  pr: Github,
  github_issue: Github,
  jira: Jira,
} as const;

const SourceCardsComponent = ({ source, showCount = true, count }: Props) => {
  const handleClick = () => {
    if (!source.htmlUrl) {
      return;
    }

    window.open(source.htmlUrl, '_blank', 'noopener,noreferrer');
  };

  const Icon = SOURCE_ICON_MAP[source.sourceType];

  const dateText = source.date?.trim() ? source.date : '-';
  const authorText = source.author?.trim() ? source.author : '-';
  return (
    <div className="flex flex-col gap-2">
      <div
        onClick={handleClick}
        className="hover:bg-neutral-2 flex w-107 cursor-pointer flex-col gap-1.5 rounded-xl bg-white p-2.5"
      >
        {/* 제목 */}
        <div className="itmes-center flex gap-1.5">
          <div className="bg-blue-5 relative right-px flex items-center gap-1.5 rounded-full px-2 py-1">
            <Icon className="h-4 w-4" />
            {showCount && <span className="text-body-xsmall text-gray-70 relative top-px">{count ?? 0}</span>}
          </div>
          <div className="flex w-90 cursor-pointer px-1.5 py-1">
            <div className="text-body-xsmall truncate text-gray-50">{source.repo}</div>
          </div>
        </div>
        {/* 소제목 */}
        <div className="text-heading-small text-gray-70 max-w-101 truncate">{source.title}</div>
        {/* 내용 */}
        <div className="text-label-small line-clamp-2 text-gray-50">{source.content}</div>
        {/* 날짜 */}
        <div className="text-body-xsmall text-gray-30 flex items-center gap-1">
          <span>{dateText}</span>
          <div className="bg-neutral-3 mx-2 h-3.75 w-px" />
          <span>{authorText}</span>
        </div>
      </div>
    </div>
  );
};

export default SourceCardsComponent;
