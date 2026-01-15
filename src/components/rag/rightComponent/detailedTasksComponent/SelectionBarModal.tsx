import clsx from 'clsx';
import { useState } from 'react';
import Epic from '/public/icons/icon/epic.svg';
import DropDownDown from '/public/icons/icon/dropdown_down.svg';
import Cancel from '/public/icons/icon/cancel_small.svg';
import Reply from '/public/icons/icon/reply.svg';
import CheckboxChecked from '/public/icons/icon/task.svg';
import Edit from '/public/icons/icon/edit_square.svg';
import Share from '/public/icons/icon/share_2.svg';
import ToolTip from '@/components/common/ToolTip';
import { useEscapeKey } from '@/hooks/useEscapeKey';

interface SelectionBarModalProps {
  onClose: () => void;
  selectedTasks: Array<{
    taskId: number;
    taskTitle: string;
    subtasks: Array<{ id: number; title: string }>;
  }>;
  totalCheckedCount: number;
  onSubtaskToggle: (taskId: number, subId: number) => void;
}

const SelectionBarModal = ({ onClose, selectedTasks, totalCheckedCount, onSubtaskToggle }: SelectionBarModalProps) => {
  const [expandedTasks, setExpandedTasks] = useState<Record<number, boolean>>(
    Object.fromEntries(selectedTasks.map((task) => [task.taskId, true])),
  );
  const [isCollapsed, setIsCollapsed] = useState(false);

  const toggleTaskExpansion = (taskId: number) => {
    setExpandedTasks((prev) => ({ ...prev, [taskId]: !prev[taskId] }));
  };

  useEscapeKey(onClose);

  return (
    <div className="absolute bottom-3.5 flex flex-col gap-2">
      <div
        className={clsx(
          'border-neutral-5 shadow-selection-bar flex w-117 flex-col border bg-white',
          isCollapsed ? 'h-14 items-center rounded-full p-2.5' : 'h-54.5 rounded-xl p-2.5 pb-0',
        )}
      >
        {/* 상위 task 및 하위 업무들 */}
        {!isCollapsed && (
          <>
            <div className="flex h-40 w-112 flex-col overflow-y-auto">
              {selectedTasks.map((task) => {
                const isExpanded = expandedTasks[task.taskId];
                return (
                  <div key={task.taskId} className="flex flex-col gap-0.5">
                    {/* 상위 task */}
                    <div className="group hover:bg-neutral-2 flex h-9 w-112 cursor-pointer gap-3 rounded-lg p-1">
                      <div className="flex min-w-0 flex-1 items-center gap-2">
                        <div className="h-4.5 w-4.5 shrink-0">
                          <Epic />
                        </div>
                        <span className="text-body-small text-gray-80 min-w-0 flex-1 truncate">{task.taskTitle}</span>
                      </div>
                      <button
                        onClick={() => toggleTaskExpansion(task.taskId)}
                        className="flex cursor-pointer items-center gap-0.5"
                      >
                        <span className="text-body-xsmall text-blue-55 flex items-center">{task.subtasks.length}</span>
                        <span className="h-4 w-4">
                          <DropDownDown
                            className={clsx(
                              'relative bottom-px flex text-blue-50 transition-transform',
                              isExpanded && 'relative top-[0.5px] rotate-180',
                            )}
                          />
                        </span>
                      </button>
                      <div className="flex items-center gap-0.5">
                        <span className="hover:bg-neutral-3 text-body-xsmall text-gray-70 relative top-px hidden cursor-pointer items-center rounded-full px-1.5 py-1 group-hover:flex">
                          상세보기
                        </span>
                        <div className="flex h-6 w-6 cursor-pointer items-center">
                          <Cancel className="text-gray-70 flex items-center" />
                        </div>
                      </div>
                    </div>
                    {/* 하위 task */}
                    {isExpanded &&
                      task.subtasks.map((subtask) => (
                        <div
                          key={subtask.id}
                          className="group hover:bg-neutral-2 flex h-9 cursor-pointer items-center gap-1 rounded-lg p-1 transition-all duration-200"
                        >
                          <div className="h-4.5 w-4.5">
                            <Reply className="text-gray-20" />
                          </div>
                          <button
                            onClick={() => onSubtaskToggle(task.taskId, subtask.id)}
                            className="h-4.5 w-4.5 cursor-pointer"
                          >
                            <CheckboxChecked />
                          </button>
                          <span className="text-body-small text-gray-80 max-w-92 min-w-0 flex-1 truncate">
                            {subtask.title}
                          </span>
                          <div className="flex items-center gap-0.5">
                            <span className="hover:bg-neutral-3 text-body-xsmall text-gray-70 hidden cursor-pointer items-center rounded-full px-1.5 py-1 group-hover:flex">
                              상세보기
                            </span>
                            <button
                              onClick={() => onSubtaskToggle(task.taskId, subtask.id)}
                              className="flex h-6 w-6 cursor-pointer items-center"
                            >
                              <Cancel className="text-gray-70" />
                            </button>
                          </div>
                        </div>
                      ))}
                  </div>
                );
              })}
            </div>
            {/* divider */}
            <div className="bg-neutral-2 relative right-2.5 mb-0.5 h-px w-116.25" />
          </>
        )}
        {/* task 버튼 */}
        <div className={clsx('flex h-14 w-112 items-center justify-between', isCollapsed && 'relative bottom-px')}>
          <div className="flex items-center gap-1.5 pl-1">
            <button
              onClick={() => setIsCollapsed(!isCollapsed)}
              className="icon-button-only-gray flex h-4.5 w-4.5 cursor-pointer p-0.5"
            >
              <DropDownDown
                className={clsx('text-gray-70 transition-transform', !isCollapsed ? 'rotate-0' : 'rotate-180')}
              />
            </button>
            <span>
              <div className="text-heading-small flex gap-0.5">
                <span className="text-blue-55">{totalCheckedCount}</span>
                <span className="text-gray-70">개의 업무 선택됨</span>
              </div>
            </span>
          </div>
          <div className="flex items-center gap-2">
            <button className="capsule-button-outline-blue flex cursor-pointer gap-1.5 px-3 py-1.5">
              <div className="relative top-px flex h-5 w-5 items-center">
                <Edit className="text-blue-50" />
              </div>
              <span className="text-blue-55 text-body-small">인수인계 시작하기</span>
            </button>
            <button className="capsule-button-solid-primary flex cursor-pointer gap-1.5 px-3 py-1.5">
              <div className="relative top-px flex h-5 w-5 items-center">
                <Share className="" />
              </div>
              <span className="text-body-small">자료 공유</span>
            </button>
          </div>
        </div>
      </div>
      <div className="flex w-117 justify-center">
        <div className="group relative">
          <button
            onClick={onClose}
            className="text-button-secondary-mono shadow-button border-neutral-3 flex h-9 w-9 cursor-pointer items-center justify-center border p-1.5"
          >
            <Cancel className="text-gray-70 h-6 w-6" />
            <div className="relative top-6 left-1/2">
              <ToolTip text="전체 선택 취소" />
            </div>
          </button>
        </div>
      </div>
    </div>
  );
};

export default SelectionBarModal;
