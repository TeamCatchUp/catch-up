export default function Mail() {
  return (
    <>
      <div className="flex justify-between">
        <span className="text-body-small text-gray-50">답변이 마음에 들지 않은 이유가 무엇인가요?</span>
        <div className="icon-button-only-gray flex cursor-pointer items-center rounded-full p-0.5">
          <div className="h-4.5 w-4.5 border text-gray-50" />
        </div>
      </div>
      <div className="flex flex-wrap gap-x-2.5 gap-y-1.5">
        <button className="box-button-outline-gray border-neutral-3 text-xsmall text-gray-80 cursor-pointer rounded-lg border px-2 py-1">
          피드백피드백
        </button>
      </div>

      {/* 더 자세히 모달 */}

      <div className="text-body-medium border-blue-30 mt-4 flex h-22.25 w-184.75 flex-col rounded-2xl border bg-white px-3 py-2.5">
        <textarea
          placeholder="자세한 피드백을 남겨주세요."
          className="text-gray-80 placeholder:text-gray-30 resize-none outline-none"
        />
        <button className="text-body-small capsule-button-solid-primary h-9 w-12.5 self-end px-3 py-1.5">제출</button>
      </div>
    </>
  );
  // <div className="flex items-center justify-center">수신함 페이지</div>;
}
