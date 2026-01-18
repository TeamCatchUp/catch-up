import clsx from 'clsx';
import Lock from '/public/icons/icon/lock_filled.svg';

type TabType = 'info' | 'files' | 'wiki' | 'url' | 'comments' | 'notion' | 'slack';

interface Tab {
  id: TabType;
  label: string;
  count: number;
  locked: boolean;
}

interface TaskDetailTabsProps {
  tabs: Tab[];
  activeTab: TabType;
  onChange: (tab: TabType) => void;
}

const OptionalNavbar = ({ tabs, activeTab, onChange }: TaskDetailTabsProps) => {
  return (
    <>
      {/* option bar */}
      <div className="mt-3.5 flex h-12 gap-5 overflow-x-auto">
        {tabs.map((tab) => (
          <button
            key={tab.id}
            onClick={() => !tab.locked && onChange(tab.id)}
            className={clsx(
              'relative flex shrink-0 items-center justify-center gap-1.5',
              tab.locked ? 'cursor-not-allowed' : 'cursor-pointer',
            )}
          >
            <span
              className={clsx(
                'text-heading-small relative',
                tab.locked ? 'text-gray-50' : activeTab === tab.id ? 'text-blue-55' : 'text-gray-50',
              )}
            >
              {tab.label}
            </span>
            {tab.locked ? (
              <Lock className="h-3.5 w-3.5 text-gray-50" />
            ) : (
              tab.count > 0 && (
                <span
                  className={clsx(
                    'text-body-xsmall rounded-md2 flex h-5 w-5 items-center justify-center text-center',
                    activeTab === tab.id ? 'bg-blue-50 text-white' : 'bg-neutral-3 text-gray-50',
                  )}
                >
                  {tab.count}
                </span>
              )
            )}
            {activeTab === tab.id && !tab.locked && (
              <div className="bg-blue-45 absolute right-0 bottom-1.75 left-0 z-50 h-0.5 translate-y-1.5" />
            )}
          </button>
        ))}
      </div>
      <span className="bg-neutral-3 relative bottom-2.75 flex h-px" />
    </>
  );
};

export default OptionalNavbar;
