import SourceFile from '/public/icons/icon/source-file.svg';

const RagSourceSkeleton = () => {
  return (
    <div className="w-116.7 mt-2 flex flex-col items-center justify-center gap-5">
      <div className="bg-blue-1 flex w-116 animate-pulse flex-col items-center justify-center gap-5 rounded-2xl p-5">
        <SourceFile className="h-23 w-28.75" />
        <span className="text-body-small text-gray-30 whitespace-nowrap">관련 상세 업무를 분석하는 중입니다.</span>
      </div>
      <div className="flex animate-pulse flex-col gap-5">
        <div className="bg-neutral-1 h-7.5 w-116 rounded-lg"></div>
        <div className="bg-neutral-1 h-7.5 w-85.75 rounded-lg"></div>
        <div className="bg-neutral-1 h-7.5 w-74.5 rounded-lg"></div>
        <div className="bg-neutral-1 h-7.5 w-60.75 rounded-lg"></div>
        <div className="bg-neutral-1 h-7.5 w-44.5 rounded-lg"></div>
      </div>
    </div>
  );
};

export default RagSourceSkeleton;
