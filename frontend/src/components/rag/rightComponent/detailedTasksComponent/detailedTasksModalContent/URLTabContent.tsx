import Link from '/public/icons/icon/link.svg';

const URLTabContent = () => {
  return (
    <div className="flex flex-col gap-2.5">
      <button className="border-neutral-3 bg-neutral-1 flex h-11 w-98 cursor-pointer items-center gap-2.5 rounded-xl border px-3 py-1.5">
        <Link className="h-5 w-5 shrink-0 text-gray-50" />
        <span className="text-body-small text-gray-70 truncate">일본 시장 진출 전략 수립 및 초기 셋업</span>
      </button>
      <button className="border-neutral-3 bg-neutral-1 flex h-11 w-98 cursor-pointer items-center gap-2.5 rounded-xl border px-3 py-1.5">
        <Link className="h-5 w-5 shrink-0 text-gray-50" />
        <span className="text-body-small text-gray-70 truncate">일본 시장 진출 전략 수립 및 초기 셋업</span>
      </button>
      <button className="border-neutral-3 bg-neutral-1 flex h-11 w-98 cursor-pointer items-center gap-2.5 rounded-xl border px-3 py-1.5">
        <Link className="h-5 w-5 shrink-0 text-gray-50" />
        <span className="text-body-small text-gray-70 truncate">일본 시장 진출 전략 수립 및 초기 셋업</span>
      </button>
    </div>
  );
};

export default URLTabContent;
