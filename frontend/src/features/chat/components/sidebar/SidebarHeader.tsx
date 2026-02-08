import clsx from 'clsx';

interface Props {
  activeTab: 'source' | 'detail';
  onChange: (tab: 'source' | 'detail') => void;
  sourceCount: number;
}

const SidebarHeader = ({ activeTab, onChange, sourceCount }: Props) => {
  return (
    <div className="sticky top-0 z-100 flex bg-white">
      <div className={`border-b-neutral-3 flex w-full items-center justify-center border-b px-4 py-1.5`}>
        <div className="border-neutral-1 bg-neutral-1 flex gap-0.5 rounded-full border p-0.5">
          <button
            onClick={() => onChange('source')}
            className={clsx(
              'text-heading-small text-gray-70 cursor-pointer rounded-full px-7 py-1.5 transition',
              activeTab === 'source' ? 'shadow-button border-neutral-3 bg-white' : 'bg-neutral-1',
            )}
          >
            출처 {sourceCount}개
          </button>
          <button
            onClick={() => onChange('detail')}
            className={clsx(
              'text-heading-small text-gray-70 cursor-pointer rounded-full px-7 py-1.5 transition',
              activeTab === 'detail' ? 'shadow-button border-neutral-3 bg-white' : 'bg-neutral-1',
            )}
          >
            Jira 티켓
          </button>
        </div>
      </div>
    </div>
  );
};

export default SidebarHeader;
