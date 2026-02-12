import Help from '/public/icons/icon/help.svg';

interface Props {
  sourceCount: number;
}

const SidebarHeader = ({ sourceCount }: Props) => {
  return (
    <div className="border-b-neutral-3 flex h-13 items-center justify-between border-b bg-white px-4 py-1.5">
      <div className="text-heading-medium text-gray-70 flex items-center gap-1.5 whitespace-nowrap">
        <span>출처</span>
        <span>{sourceCount}개</span>
      </div>

      <div className="bg-neutral-2 flex items-center gap-1 rounded-md2 px-1.5 py-0.5">
        <div className="flex h-6 w-6 items-center justify-center">
          <Help className="h-4 w-4 text-gray-50" />
        </div>
        <div className="text-body-xsmall text-gray-50 truncate whitespace-nowrap">
          AI 답변 근거 자료
        </div>
      </div>
    </div>
  );
};

export default SidebarHeader;
