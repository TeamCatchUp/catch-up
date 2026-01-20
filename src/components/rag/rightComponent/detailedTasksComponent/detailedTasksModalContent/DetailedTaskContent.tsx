import { ReactNode } from 'react';
import RelatedTasksSection from './RelatedTasksSection';

interface DetailedTaskContentProps {
  activeTab: string;
  renderContent: () => ReactNode;
  type: 'task' | 'subtask';
  currentTask?: Task;
}

const DetailedTaskContent = ({ activeTab, renderContent, type, currentTask }: DetailedTaskContentProps) => {
  return (
    <div className="mt-4 flex flex-1 flex-col overflow-y-auto">
      {/* content */}
      {renderContent()}

      {activeTab !== 'comments' && (
        <div className="mt-6 flex flex-col gap-4">
          {/* divider */}
          <div className="border-neutral-3 flex border" />
          <RelatedTasksSection type={type} currentTask={currentTask} />
        </div>
      )}
    </div>
  );
};

export default DetailedTaskContent;
