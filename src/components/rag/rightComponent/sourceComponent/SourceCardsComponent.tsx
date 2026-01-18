import clsx from 'clsx';
import File from '/public/icons/icon/file.svg';
import Wiki from '/public/icons/logo/Wiki.svg';
import Link from '/public/icons/icon/link.svg';
import Github from '/public/icons/logo/GitHub.svg';
import Slack from '/public/icons/logo/Slack.svg';
import Comment from '/public/icons/icon/chat.svg';

interface Props {
  source: ChatSource;
  showCount?: boolean;
  count?: number;
}

const SOURCE_ICON_MAP: Record<ChatSource['sourceType'], React.FC<any>> = {
  file: File,
  wiki: Wiki,
  url: Link,
  github: Github,
  slack: Slack,
  comment: Comment,
} as const;

const SourceCardsComponent = ({ source, showCount = true, count }: Props) => {
  const handleClick = () => {
    if (!source.htmlUrl) {
      // console.log('url 없음');
      return;
    }

    window.open(source.htmlUrl, '_blank', 'noopener,noreferrer');
  };

  const Icon = SOURCE_ICON_MAP[source.sourceType] ?? Link;

  // 중간시연용
  const fileName = source.htmlUrl ? source.htmlUrl.split('/').pop() : source.title;

  return (
    // <div className="flex flex-col gap-2">
    //   <div
    //     onClick={handleClick}
    //     className="hover:bg-neutral-2 flex w-93.25 cursor-pointer flex-col gap-1.5 rounded-xl bg-white p-2.5"
    //   >
    //     {/* 제목 */}
    //     <div className="flex gap-1.5">
    //       <div className="shadow-button border-neutral-2 flex h-7 w-7 items-center justify-center border">
    //         <Icon className="h-5 w-5" />
    //       </div>
    //       <div className="flex cursor-pointer px-1.5 py-1">
    //         <div className="text-gray-70 text-body-xsmall truncate">{fileName}</div>
    //         <ArrowRight className="text-gray-30 h-5 w-5" />
    //       </div>
    //     </div>
    //     {/* 소제목 */}
    //     <div className="text-body-small text-gray-70 truncate">{source.subtitle}</div>
    //     {/* 내용 */}
    //     <div className="text-body-xsmall line-clamp-2 text-gray-50">{source.content}</div>
    //     {/* 날짜 */}
    //     <div className="text-body-xsmall text-gray-30">{source.date}</div>
    //   </div>
    // </div>
    <div className="flex flex-col gap-2">
      <div className="hover:bg-neutral-2 flex w-93.25 cursor-pointer flex-col gap-1.5 rounded-xl bg-white p-2.5">
        {/* 제목 */}
        <div onClick={handleClick} className="itmes-center flex gap-1.5">
          <div className="bg-blue-5 flex items-center gap-1.5 rounded-full px-2 py-1">
            <Icon className="h-4 w-4" />
            {showCount && <span className="text-body-xsmall text-gray-70 relative top-px">{count ?? 0}</span>}
          </div>
          <div className="flex w-76 cursor-pointer px-1.5 py-1">
            <div className="text-body-xsmall truncate text-gray-50">{source.title}</div>
          </div>
        </div>
        {/* 소제목 */}
        <div className="text-body-small text-gray-70 max-w-87 truncate">{source.subtitle}</div>
        {/* 내용 */}
        <div className="text-body-xsmall line-clamp-2 text-gray-50">{source.content}</div>
        {/* 날짜 */}
        <div className="text-body-xsmall text-gray-30 flex items-center gap-1">
          <span>{source.date}</span>
          <div className="bg-neutral-3 mx-2 h-3.75 w-px" />
          <span>작성자 명</span>
        </div>
      </div>

      {/* divider
      <div className="bg-neutral-4 mt-1 mb-4 h-px w-93.25" /> */}

      {/* 참고하면 좋은 문서들
      <div className="flex flex-col gap-2.5">

        <div className="flex items-center gap-1.5 px-1.5">
          <AddCircle className="text-gray-70 h-5 w-5" />
          <span className="text-body-small text-gray-70 relative top-[1.5px]">참고하면 좋은 문서들</span>
        </div>
      </div> */}
    </div>
  );
};

export default SourceCardsComponent;
