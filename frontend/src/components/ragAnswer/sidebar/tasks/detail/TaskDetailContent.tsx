import { ReactNode } from 'react';
import RelatedTasksSection from './RelatedTasksSection';

interface TaskDetailContentProps {
  activeTab: string;
  renderContent: () => ReactNode;
  type: 'task' | 'subtask';
  currentTask?: JiraTask;
}

const TaskDetailContent = ({ activeTab, renderContent, type, currentTask }: TaskDetailContentProps) => {
  return (
    <div className="mt-4 flex flex-1 flex-col overflow-y-auto">
      {/* content */}
      {renderContent()}

      {activeTab !== 'comments' && (
        <div className="mt-6 flex flex-col gap-4">
          {/* divider */}
          <div className="bg-neutral-3 flex h-px" />
          <RelatedTasksSection type={type} currentTask={currentTask} />
        </div>
      )}
    </div>
  );
};

export default TaskDetailContent;
