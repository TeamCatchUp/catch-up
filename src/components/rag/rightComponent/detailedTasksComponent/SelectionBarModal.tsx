'use client';

import clsx from 'clsx';
import { useState, useEffect } from 'react';
import Epic from '/public/icons/icon/epic.svg';
import DropDownDown from '/public/icons/icon/dropdown_down.svg';
import Cancel from '/public/icons/icon/cancel_small.svg';
import Reply from '/public/icons/icon/reply.svg';
import Task from '/public/icons/icon/task.svg';
import Edit from '/public/icons/icon/edit_square.svg';
import Share from '/public/icons/icon/share_2.svg';
import ToolTip from '@/components/common/ToolTip';

interface SelectionBarModalProps {
  onClose: () => void;
  onClearAll: () => void;
  selectedTasks: Array<{
    taskId: string;
    taskTitle: string;
    taskChecked: boolean;
    subtasks: Array<{ id: string; title: string }>;
  }>;
  totalCheckedCount: number;
  onTaskToggle: (taskId: string) => void;
  onSubtaskToggle: (taskId: string, subId: string) => void;

  isCollapsed: boolean;
  onToggleCollapse: () => void;
  onOpenDetail: (payload: { type: 'task' | 'subtask'; taskId: string; subId?: string }) => void;
}

const SelectionBarModal = ({
  onClose,
  onClearAll,
  selectedTasks,
  totalCheckedCount,
  onTaskToggle,
  onSubtaskToggle,
  isCollapsed,
  onToggleCollapse,
  onOpenDetail,
}: SelectionBarModalProps) => {
  const [expandedTasks, setExpandedTasks] = useState<Record<string, boolean>>(
    Object.fromEntries(selectedTasks.map((task) => [task.taskId, true])),
  );

  const toggleTaskExpansion = (taskId: string) => {
    setExpandedTasks((prev) => ({ ...prev, [taskId]: !prev[taskId] }));
  };

  const handleClearAll = () => {
    onClearAll();
    onClose();
  };

  // useEscapeKey(onClose);

  useEffect(() => {
    setExpandedTasks((prev) => {
      const newState = { ...prev };
      selectedTasks.forEach((task) => {
        // 새로 추가된 task (한 번에 checked 되지 않은 task)
        if (prev[task.taskId] === undefined) {
          newState[task.taskId] = task.taskChecked;
        }
        // 하위 업무 check -> 해당 상위 업무 check 시 자동 expanded
        else if (!task.taskChecked && prev[task.taskId] === false) {
          newState[task.taskId] = true;
        }
      });
      return newState;
    });
  }, [selectedTasks]);

  return (
    <div className="pointer-events-none absolute bottom-8 flex flex-col gap-2">
      <div
        className={clsx(
          'border-neutral-5 shadow-selection-bar pointer-events-auto flex w-117 flex-col border bg-white',
          isCollapsed ? 'h-14 items-center rounded-full p-2.5' : 'h-54.5 rounded-xl p-2.5 pb-0',
        )}
      >
        {/* 상위 task 및 하위 업무들 */}
        {!isCollapsed && (
          <>
            <div className="flex h-40 w-108.75 flex-col overflow-y-auto">
              {selectedTasks.map((task) => {
                const isExpanded = expandedTasks[task.taskId];
                const showParentTask = task.taskChecked;

                return (
                  <div key={task.taskId} className="flex flex-col gap-0.5">
                    {/* 상위 task */}
                    {showParentTask && (
                      <div className="group hover:bg-neutral-2 flex h-9 w-103.75 gap-3 rounded-lg p-1">
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
                          <span className="text-body-xsmall text-blue-55 flex items-center">
                            {task.subtasks.length}
                          </span>
                          <span className="h-4 w-4">
                            <DropDownDown
                              className={clsx(
                                'flex text-blue-50 transition-transform',
                                isExpanded ? 'relative bottom-px rotate-180' : 'relative bottom-0.5',
                              )}
                            />
                          </span>
                        </button>
                        <div className="flex items-center gap-0.5">
                          <button
                            onClick={() => onOpenDetail({ type: 'task', taskId: task.taskId })}
                            className="hover:bg-neutral-3 text-body-xsmall text-gray-70 relative top-px hidden cursor-pointer items-center rounded-full px-1.5 py-1 group-hover:flex"
                          >
                            상세보기
                          </button>
                          <button
                            onClick={() => onTaskToggle(task.taskId)}
                            className="flex h-6 w-6 cursor-pointer items-center"
                          >
                            <Cancel className="text-gray-70 flex items-center" />
                          </button>
                        </div>
                      </div>
                    )}
                    {/* 하위 task */}
                    {(showParentTask ? isExpanded : true) &&
                      task.subtasks.map((subtask) => (
                        <div
                          key={subtask.id}
                          className="group hover:bg-neutral-2 flex h-9 items-center gap-1 rounded-lg p-1 transition-all duration-200"
                        >
                          {showParentTask && (
                            <div className="h-4.5 w-4.5">
                              <Reply className="text-gray-20" />
                            </div>
                          )}
                          <button className="h-4.5 w-4.5">
                            <Task />
                          </button>
                          <span
                            className={clsx(
                              'text-body-small text-gray-80 min-w-0 flex-1 truncate',
                              showParentTask ? 'max-w-88.75' : 'w-92.25',
                            )}
                          >
                            {subtask.title}
                          </span>
                          <div className="flex items-center gap-0.5">
                            <button
                              onClick={() => onOpenDetail({ type: 'subtask', taskId: task.taskId, subId: subtask.id })}
                              className="hover:bg-neutral-3 text-body-xsmall text-gray-70 hidden cursor-pointer items-center rounded-full px-1.5 py-1 group-hover:flex"
                            >
                              상세보기
                            </button>
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
            <div className="bg-neutral-2 relative right-2.5 mb-0.5 h-px w-103.75" />
          </>
        )}
        {/* task 버튼 */}
        <div className={clsx('flex h-14 w-101.25 items-center justify-between', isCollapsed && 'relative bottom-px')}>
          <div className="flex items-center gap-1.5 pl-1">
            <button onClick={onToggleCollapse} className="icon-button-only-gray flex h-4.5 w-4.5 cursor-pointer p-0.5">
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
      <div className="group pointer-events-auto relative left-53 w-9">
        <button
          onClick={handleClearAll}
          className="text-button-secondary-mono shadow-button border-neutral-3 pointer-events-auto flex h-9 w-9 cursor-pointer items-center justify-center border p-1.5"
        >
          <Cancel className="text-gray-70 h-6 w-6" />
          <div className="relative bottom-4.25 left-1">
            <ToolTip text="전체 선택 취소" />
          </div>
        </button>
      </div>
    </div>
  );
};

export default SelectionBarModal;
