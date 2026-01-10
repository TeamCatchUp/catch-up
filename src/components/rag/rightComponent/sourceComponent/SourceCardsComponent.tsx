import Github from '/public/icons/logo/GitHub.svg';
import ArrowRight from '/public/icons/icon/arrow_right.svg';

interface Props {
  source: ChatSource;
}

const SourceCardsComponent = ({ source }: Props) => {
  const handleClick = () => {
    if (!source.htmlUrl) {
      // console.log('url 없음');
      return;
    }

    window.open(source.htmlUrl, '_blank', 'noopener,noreferrer');
  };

  // 중간시연용
  const fileName = source.htmlUrl ? source.htmlUrl.split('/').pop() : source.title;

  return (
    <div className="flex flex-col gap-2">
      <div
        onClick={handleClick}
        className="hover:bg-neutral-2 flex w-93.25 cursor-pointer flex-col gap-1.5 rounded-xl bg-white p-2.5"
      >
        {/* 제목 */}
        <div className="flex gap-1.5">
          <div className="shadow-button border-neutral-2 flex h-7 w-7 items-center justify-center border">
            <Github className="h-5 w-5" />
          </div>
          <div className="flex cursor-pointer px-1.5 py-1">
            <div className="text-gray-70 text-body-xsmall truncate">{fileName}</div>
            <ArrowRight className="text-gray-30 h-5 w-5" />
          </div>
        </div>
        {/* 소제목 */}
        <div className="text-body-small text-gray-70 truncate">{source.subtitle}</div>
        {/* 내용 */}
        <div className="text-body-xsmall line-clamp-2 text-gray-50">{source.content}</div>
        {/* 날짜 */}
        <div className="text-body-xsmall text-gray-30">{source.date}</div>
      </div>
    </div>
  );
};

export default SourceCardsComponent;
