'use client';

import clsx from 'clsx';
import { useState } from 'react';
import DropDownDown from '/public/icons/icon/dropdown_down.svg';

interface RelatedTasksSectionProps {
  type: 'task' | 'subtask';
  currentTask: JiraTask | undefined;
}

const RelatedTasksSection = ({ type, currentTask }: RelatedTasksSectionProps) => {
  const [isOpen, setIsOpen] = useState(true);

  if (!currentTask) return null;

  if (type === 'task') {
    const subtasks = currentTask.subtasks || [];
    if (subtasks.length === 0) return null;

    return (
      <>
        <div className="flex gap-1.5">
          <button onClick={() => setIsOpen(!isOpen)} className="cursor-pointer">
            <DropDownDown className={clsx('text-gray-70 h-4.5 w-4.5 transition-transform', isOpen && 'rotate-180')} />
          </button>
          <span className="text-heading-small text-gray-80">하위 업무</span>
          <span className="text-heading-small text-blue-40">{subtasks.length}</span>
        </div>
        {isOpen && (
          <div className="text-body-small text-gray-70 flex max-w-98 flex-wrap gap-x-3 gap-y-2.5">
            {subtasks.map((sub) => (
              <span key={sub.id} className="capsule-button-outline-light-blue truncate px-3 py-1.5">
                {sub.title}
              </span>
            ))}
          </div>
        )}
      </>
    );
  } else {
    return (
      <>
        <div className="flex gap-1.5">
          <button onClick={() => setIsOpen(!isOpen)} className="cursor-pointer">
            <DropDownDown className={clsx('text-gray-70 h-4.5 w-4.5 transition-transform', isOpen && 'rotate-180')} />
          </button>
          <span className="text-heading-small text-gray-80">상위 업무</span>
          <span className="text-heading-small text-blue-40">1</span>
        </div>
        {isOpen && (
          <div className="text-body-small text-gray-70 flex max-w-98 flex-wrap gap-x-3 gap-y-2.5">
            <span className="capsule-button-outline-purple truncate px-3 py-1.5">{currentTask.title}</span>
          </div>
        )}
      </>
    );
  }
};

export default RelatedTasksSection;
