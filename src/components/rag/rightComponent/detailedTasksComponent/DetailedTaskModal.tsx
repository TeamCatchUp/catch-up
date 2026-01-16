import clsx from 'clsx';
import { useState } from 'react';
import DropDownDown from '/public/icons/icon/dropdown_down.svg';
import Kebab from '/public/icons/icon/kebab.svg';
import Cancel from '/public/icons/icon/cancel.svg';
import Check from '/public/icons/icon/check.svg';
import Edit from '/public/icons/icon/edit_square.svg';
import Share from '/public/icons/icon/share_2.svg';
import Lock from '/public/icons/icon/lock_filled.svg';
import InfoTabContent from './detailedTasksModalContent/InfoTabContent';
import FilesTabContent from './detailedTasksModalContent/FilesTabContent';
import WikiTabContent from './detailedTasksModalContent/WikiTabContent';
import URLTabContent from './detailedTasksModalContent/URLTabContent';
import CommentsTabContent from './detailedTasksModalContent/CommentsTabContent';
import NoDataContent from './detailedTasksModalContent/NoDataContent';
import RelatedTasksSection from './detailedTasksModalContent/RelatedTasksSection';
import { useEscapeKey } from '@/hooks/useEscapeKey';

interface DetailedTaskModalProps {
  onClose: () => void;
  data: {
    type: 'task' | 'subtask';
    taskId: number;
    subId?: number;
  };
  tasks: Task[];
  checkedMap: Record<number, { checked: boolean; subtasks: Record<number, boolean> }>;
  onToggleCheck: (taskId: number, subId?: number) => void;
}

type TabType = 'info' | 'files' | 'wiki' | 'url' | 'comments' | 'notion' | 'slack';

const DetailedTaskModal = ({ onClose, data, tasks, checkedMap, onToggleCheck }: DetailedTaskModalProps) => {
  const [activeTab, setActiveTab] = useState<TabType>('info');

  useEscapeKey(onClose);

  const tabs = [
    { id: 'info' as TabType, label: 'Info', count: 0, locked: false },
    { id: 'files' as TabType, label: '첨부파일', count: 2, locked: false },
    { id: 'wiki' as TabType, label: 'Wiki', count: 1, locked: false },
    { id: 'url' as TabType, label: 'URL', count: 0, locked: false },
    { id: 'comments' as TabType, label: '댓글', count: 5, locked: false },
    { id: 'notion' as TabType, label: 'Notion', count: 0, locked: true },
    { id: 'slack' as TabType, label: 'Slack', count: 0, locked: true },
  ];

  const currentTask = tasks.find((t) => t.id === data.taskId);
  const currentSubTask = data.type === 'subtask' ? currentTask?.subtasks.find((s) => s.id === data.subId) : null;
  const taskTitle = data.type === 'task' ? currentTask?.title : currentSubTask?.title;
  const isChecked =
    data.type === 'task' ? checkedMap[data.taskId]?.checked : checkedMap[data.taskId]?.subtasks[data.subId!];

  const renderTabContent = () => {
    const tab = tabs.find((t) => t.id === activeTab);

    if (tab?.count === 0 && activeTab !== 'info') {
      return <NoDataContent />;
    }

    switch (activeTab) {
      case 'info':
        return <InfoTabContent />;
      case 'files':
        return <FilesTabContent />;
      case 'wiki':
        return <WikiTabContent />;
      case 'url':
        return <URLTabContent />;
      case 'comments':
        return <CommentsTabContent />;
      default:
        return <NoDataContent />;
    }
  };

  const handleTabClick = (tab: (typeof tabs)[0]) => {
    if (!tab.locked) {
      setActiveTab(tab.id);
    }
  };

  const handleCheckToggle = () => {
    if (data.type === 'task') {
      onToggleCheck(data.taskId);
    } else {
      onToggleCheck(data.taskId, data.subId);
    }
  };

  return (
    <div className="shadow-rag-bar border-neutral-4 absolute bottom-4 ml-8 flex h-145 w-108.75 flex-col rounded-2xl border bg-white p-5">
      {/* TopMenuBar */}
      <div className="flex justify-between">
        <div className="flex gap-1.5">
          <button className="rounded-md2! box-button-outline-gray h-7.5 w-7.5 cursor-pointer p-1">
            <DropDownDown className="h-5 w-5 rotate-180" />
          </button>
          <button className="rounded-md2! box-button-outline-gray h-7.5 w-7.5 cursor-pointer p-1">
            <DropDownDown className="h-5 w-5" />
          </button>
        </div>
        <div className="-mr-px flex items-center justify-center gap-1.5">
          <button className="icon-button-only-gray flex h-7 w-7 cursor-pointer items-center justify-center rounded-full! p-0.5">
            <Kebab className="h-5 w-5 text-gray-50" />
          </button>
          <button
            onClick={onClose}
            className="icon-button-only-gray flex h-7 w-7 cursor-pointer items-center justify-center rounded-full! p-0.5"
          >
            <Cancel className="h-5 w-5 text-gray-50" />
          </button>
        </div>
      </div>
      {/* title */}
      <div className="mt-4 flex max-h-14.5 items-center gap-2.5">
        <button
          onClick={handleCheckToggle}
          className={clsx(
            'flex h-8.5 w-8.5 cursor-pointer items-center justify-center rounded-lg border p-1.5',
            isChecked ? 'border-blue-45 bg-blue-1' : 'border-neutral-3 bg-neutral-1',
          )}
        >
          <Check className={clsx('h-5.5 w-5.5', isChecked ? 'text-blue-50' : 'text-gray-30')} />
        </button>
        <span className="text-heading-large text-gray-70 line-clamp-2">{taskTitle}</span>
      </div>
      {/* option bar */}
      <div className="mt-3.5 flex h-12 gap-5 overflow-x-auto">
        {tabs.map((tab) => (
          <button
            key={tab.id}
            onClick={() => handleTabClick(tab)}
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

      <div className="mt-4 flex flex-1 flex-col overflow-y-auto">
        {/* content */}
        {renderTabContent()}

        {activeTab !== 'comments' && (
          <div className="mt-6 flex flex-col gap-4">
            {/* divider */}
            <div className="border-neutral-3 flex border" />
            <RelatedTasksSection type={data.type} currentTask={currentTask} />
          </div>
        )}
      </div>
      {/* 기능 버튼 */}
      <div className="mt-2 flex h-9 items-center justify-between gap-4">
        <button className="capsule-button-outline-blue flex w-48 cursor-pointer items-center justify-center gap-1.5 px-3 py-1.5">
          <div className="relative top-px flex h-5 w-5 items-center">
            <Edit className="text-blue-50" />
          </div>
          <span className="text-blue-55 text-body-small">인수인계 시작하기</span>
        </button>
        <button className="capsule-button-solid-primary flex w-48 cursor-pointer items-center justify-center gap-1.5 px-3 py-1.5">
          <div className="relative top-px flex h-5 w-5 items-center">
            <Share className="" />
          </div>
          <span className="text-body-small">자료 공유하기</span>
        </button>
      </div>
    </div>
  );
};

export default DetailedTaskModal;
