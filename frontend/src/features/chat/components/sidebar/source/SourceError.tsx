import SourceFile from '@/public/icons/icon/source-file.svg';

export default function SourceError() {
  return (
    <div className="mx-auto mt-3 flex w-full flex-col items-center justify-center gap-5">
      <div className="bg-fill-primary-assistive flex w-full flex-col items-center justify-center gap-5 rounded-2xl p-5">
        <SourceFile className="h-23 w-28.75" />
        <span className="text-body-small text-content-assistive whitespace-nowrap">
          관련 문서를 불러오지 못했습니다.
        </span>
      </div>
    </div>
  );
}
