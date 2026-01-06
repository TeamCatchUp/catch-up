import Github from '/public/icons/logo/GitHub.svg';
import ArrowRight from '/public/icons/icon/arrow_right.svg';

interface Props {
  source: {
    title: string;
    subtitle: string;
    content: string;
    date: string;
  };
}

const SourceCardsComponent = ({ source }: Props) => {
  return (
    <div className="flex flex-col gap-2">
      <div className="hover:bg-neutral-2 flex w-93.75 cursor-pointer flex-col gap-1.5 rounded-xl bg-white p-2">
        {/* 제목 */}
        <div className="flex gap-1.5">
          <div className="shadow-button border-neutral-2 flex h-7 w-7 items-center justify-center border">
            <Github className="h-5 w-5" />
          </div>
          <div className="secondary-mono flex cursor-pointer rounded-full px-1.5 py-1">
            <div className="text-gray-70 text-body-xsmall truncate">{source.title}</div>
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
