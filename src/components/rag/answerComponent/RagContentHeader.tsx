import Menu from '/public/icons/icon/menu.svg';
import ArrowRight2 from '/public/icons/icon/arrow_right2.svg';
import Add from '/public/icons/icon/add_small.svg';
import Share from '/public/icons/icon/share_2.svg';
import Kebeb from '/public/icons/icon/kebeb 2.svg';

const RagHeader = () => {
  return (
    <div className="border-r-neutral-3 border-b-neutral-3 sticky top-0 z-100 flex min-w-240.75 justify-between border-r border-b bg-white px-16 py-2">
      <div className="flex items-center">
        <button className={`box-button-outline-gray} flex items-center rounded-xl px-2 py-1`}>
          <Menu className="h-5 w-5 text-gray-50" />
          <span className={`text-heading-small ml-1.5 cursor-pointer text-gray-50`}>업무 어시스선트</span>
        </button>
        <ArrowRight2 className="h-5 w-5 text-gray-50" />
        <button className={`text-heading-small text-gray-80 icon-button-only-gray cursor-pointer rounded-xl px-2 py-1`}>
          현재 페이지
        </button>
      </div>

      <div className="flex items-center gap-1.5">
        <button
          className={`border-neutral-3 box-button-outline-gray flex w-29.75 cursor-pointer items-center gap-1.5 rounded-lg border px-2.5 py-1.5`}
        >
          <Add className="text-gray-70 flex h-5 w-5" />
          <span className={`text-body-small text-gray-70 whitespace-nowrap`}>새 업무 질문</span>
        </button>
        <button className={`icon-button-only-gray flex items-center rounded-lg p-1.5`}>
          <Share className="h-6 w-6 cursor-pointer text-gray-50" />
        </button>
        <button className={`icon-button-icon-gray flex items-center rounded-lg p-1.5`}>
          <Kebeb className="h-6 w-6 cursor-pointer text-gray-50" />
        </button>
      </div>
    </div>
  );
};

export default RagHeader;
