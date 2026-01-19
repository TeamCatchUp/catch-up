'use client';

import clsx from 'clsx';
import { useState, useMemo } from 'react';
import DropDownDown from '/public/icons/icon/dropdown_down.svg';
import CheckboxUnchecked from '/public/icons/icon/checkbox_unchecked.svg';
import CheckboxChecked from '/public/icons/icon/checkbox_checked.svg';
import Connector from '/public/icons/icon/connector.svg';
import LastConnector from '/public/icons/icon/last_connector.svg';
import DetailedTaskModal from './DetailedTaskModal';
import SelectionBarModal from './SelectionBarModal';

const MOCK_TASK: Task[] = [
  {
    id: 1,
    title: '일본 시장/경쟁사 심층 분석',
    subtasks: [
      { id: 11, title: '타겟 고객군(ICP) 정의 및 예상 시장 규모(TAM/SAM/SOM) 산출' },
      { id: 12, title: '타겟 고객군(ICP) 정의 및 예상 시장 규모(TAM/SAM/SOM) 산출' },
      { id: 13, title: '일본 내 개인정보보호법(APPI) 및 컴플라이언스 요건 검토' },
      { id: 14, title: '현지 잠재 고객 10개사 대상 FGI(Focus Group Interview) 진행' },
      { id: 15, title: '시장 진입을 위한 SWOT 분석 및 GTM 전략 초안 작성' },
    ],
  },
  {
    id: 2,
    title: '일본 시장/경쟁사 심층 분석2',
    subtasks: [
      { id: 21, title: '타겟 고객군(ICP) 정의 및 예상 시장 규모(TAM/SAM/SOM) 산출' },
      { id: 22, title: '타겟 고객군(ICP) 정의 및 예상 시장 규모(TAM/SAM/SOM) 산출' },
      { id: 23, title: '일본 내 개인정보보호법(APPI) 및 컴플라이언스 요건 검토' },
      { id: 24, title: '현지 잠재 고객 10개사 대상 FGI(Focus Group Interview) 진행' },
      { id: 25, title: '시장 진입을 위한 SWOT 분석 및 GTM 전략 초안 작성' },
    ],
  },
  {
    id: 3,
    title: '일본 시장/경쟁사 심층 분석3',
    subtasks: [
      { id: 31, title: '타겟 고객군(ICP) 정의 및 예상 시장 규모(TAM/SAM/SOM) 산출' },
      { id: 32, title: '타겟 고객군(ICP) 정의 및 예상 시장 규모(TAM/SAM/SOM) 산출' },
      { id: 33, title: '일본 내 개인정보보호법(APPI) 및 컴플라이언스 요건 검토' },
      { id: 34, title: '현지 잠재 고객 10개사 대상 FGI(Focus Group Interview) 진행' },
      { id: 35, title: '시장 진입을 위한 SWOT 분석 및 GTM 전략 초안 작성' },
    ],
  },
  {
    id: 4,
    title: '일본 시장/경쟁사 심층 분석4',
    subtasks: [
      { id: 41, title: '타겟 고객군(ICP) 정의 및 예상 시장 규모(TAM/SAM/SOM) 산출' },
      { id: 42, title: '타겟 고객군(ICP) 정의 및 예상 시장 규모(TAM/SAM/SOM) 산출' },
      { id: 43, title: '일본 내 개인정보보호법(APPI) 및 컴플라이언스 요건 검토' },
      { id: 44, title: '현지 잠재 고객 10개사 대상 FGI(Focus Group Interview) 진행' },
      { id: 45, title: '시장 진입을 위한 SWOT 분석 및 GTM 전략 초안 작성' },
    ],
  },
];

const createInitialCheckedMap = () => {
  const map: Record<
    number,
    {
      checked: boolean;
      subtasks: Record<number, boolean>;
    }
  > = {};

  MOCK_TASK.forEach((task) => {
    map[task.id] = {
      checked: false,
      subtasks: Object.fromEntries(task.subtasks.map((sub) => [sub.id, false])),
    };
  });

  return map;
};

const DetailedTasksCardComponent = () => {
  const [checkedMap, setCheckedMap] = useState(createInitialCheckedMap);
  const [openMap, setOpenMap] = useState<Record<number, boolean>>({});

  // detail modal (업무 선택)
  const [detailModal, setDetailModal] = useState<{
    type: 'task' | 'subtask';
    taskId: number;
    subId?: number;
  } | null>(null);

  // selection bar 표시 여부
  const [showSelectionBar, setShowSelectionBar] = useState(false);

  // checked tasks 개수
  const selectedTasks = useMemo(() => {
    const result: Array<{
      taskId: number;
      taskTitle: string;
      taskChecked: boolean; // 상위 업무 체크 여부
      subtasks: Array<{ id: number; title: string }>;
    }> = [];

    MOCK_TASK.forEach((task) => {
      const taskState = checkedMap[task.id];
      const checkedSubtasks = task.subtasks.filter((sub) => taskState.subtasks[sub.id]);

      if (checkedSubtasks.length > 0) {
        result.push({
          taskId: task.id,
          taskTitle: task.title,
          taskChecked: taskState.checked,
          subtasks: checkedSubtasks,
        });
      }
    });

    return result;
  }, [checkedMap]);

  const totalCheckedCount = useMemo(() => {
    return selectedTasks.reduce((sum, task) => sum + task.subtasks.length, 0);
  }, [selectedTasks]);

  // selection bar 표시 여부
  useMemo(() => {
    if (!detailModal) {
      setShowSelectionBar(totalCheckedCount > 0);
    }
  }, [totalCheckedCount]);

  // 상위 업무 (checkbox)
  const toggleTask = (task: Task) => {
    setCheckedMap((prev) => {
      const current = prev[task.id];
      const nextChecked = !current?.checked;

      return {
        ...prev,
        [task.id]: {
          checked: nextChecked,
          subtasks: Object.fromEntries(task.subtasks.map((sub) => [sub.id, nextChecked])),
        },
      };
    });

    setDetailModal(null);
  };

  // 하위 업무 (checkbox)
  const toggleSubTask = (task: Task, subId: number) => {
    setCheckedMap((prev) => {
      const taskState = prev[task.id];

      const nextSubtasks = {
        ...taskState.subtasks,
        [subId]: !taskState.subtasks[subId],
      };

      const allChecked = Object.values(nextSubtasks).every(Boolean);

      return {
        ...prev,
        [task.id]: {
          checked: allChecked,
          subtasks: nextSubtasks,
        },
      };
    });

    setDetailModal(null);
  };

  // selection bar에서 상위 업무 체크 해제 -> 해당 하위 업무도 해제
  const handleTaskToggleFromModal = (taskId: number) => {
    const task = MOCK_TASK.find((t) => t.id === taskId);
    if (task) {
      toggleTask(task);
    }
  };

  // SelectionBarModal에서 하위 업무 체크 해제
  const handleSubtaskToggleFromModal = (taskId: number, subId: number) => {
    const task = MOCK_TASK.find((t) => t.id === taskId);
    if (task) {
      toggleSubTask(task, subId);
    }
  };

  // 상세 업무 모달에서 체크 제어 (DetailTaskModal)
  const handleCheckToggleFromModal = (taskId: number, subId?: number) => {
    const task = MOCK_TASK.find((t) => t.id === taskId);
    if (!task) return;

    setCheckedMap((prev) => {
      if (subId !== undefined) {
        // 하위 업무 체크
        const taskState = prev[taskId];
        const nextSubtasks = {
          ...taskState.subtasks,
          [subId]: !taskState.subtasks[subId],
        };
        const allChecked = Object.values(nextSubtasks).every(Boolean);

        return {
          ...prev,
          [taskId]: {
            checked: allChecked,
            subtasks: nextSubtasks,
          },
        };
      } else {
        // 상위 업무 체크
        const current = prev[taskId];
        const nextChecked = !current?.checked;

        return {
          ...prev,
          [taskId]: {
            checked: nextChecked,
            subtasks: Object.fromEntries(task.subtasks.map((sub) => [sub.id, nextChecked])),
          },
        };
      }
    });
  };

  // 이동 가능한 전체 업무 목록 (업무 목록을 순서 리스트로 만듦) - 상세 업무 모달
  const flatTaskList = useMemo(() => {
    const result: Array<{
      type: 'task' | 'subtask';
      taskId: number;
      subId?: number;
    }> = [];

    MOCK_TASK.forEach((task) => {
      result.push({ type: 'task', taskId: task.id });

      task.subtasks.forEach((sub) => {
        result.push({ type: 'subtask', taskId: task.id, subId: sub.id });
      });
    });
    return result;
  }, []);

  // 현재 업무의 index 계산
  const currentIndex = useMemo(() => {
    if (!detailModal) return -1;

    return flatTaskList.findIndex(
      (item) => item.type == detailModal.type && item.taskId === detailModal.taskId && item.subId === detailModal.subId,
    );
  }, [detailModal, flatTaskList]);

  // 이전 업무 이동 핸들러 - 상세 업무 모달
  const goPrev = () => {
    if (currentIndex <= 0) return;
    setDetailModal(flatTaskList[currentIndex - 1]);
  };
  // 다음 업무 이동 핸들러 - 상세 업무 모달
  const goNext = () => {
    if (currentIndex === -1 || currentIndex >= flatTaskList.length - 1) return;
    setDetailModal(flatTaskList[currentIndex + 1]);
  };

  const handleDetailModalOpen = (type: 'task' | 'subtask', taskId: number, subId?: number) => {
    setShowSelectionBar(false);
    setDetailModal((prev) =>
      prev?.type === type && prev.taskId === taskId && prev.subId === subId ? null : { type, taskId, subId },
    );
  };

  const handleClearAll = () => {
    setCheckedMap(createInitialCheckedMap());
    setShowSelectionBar(false);
  };

  return (
    <div className="flex flex-col">
      {/* 헤더 */}
      <div className="bg-neutral-1 text-body-xsmall flex items-center justify-center rounded-t-2xl rounded-b-md py-1.5 text-gray-50">
        제목
      </div>
      {MOCK_TASK.map((task) => {
        const opened = openMap[task.id];
        const checked = checkedMap[task.id]?.checked;

        return (
          <div key={task.id} className="flex flex-col">
            {/* 상위 업무 */}
            <div
              className={clsx(
                'border-neutral-4 flex items-center border-b px-2 py-3',
                detailModal?.type === 'task' &&
                  detailModal.taskId === task.id &&
                  'rounded-md2 border-blue-30! bg-blue-1 border',
              )}
            >
              {/* dropdown */}
              <button
                onClick={() => setOpenMap((prev) => ({ ...prev, [task.id]: !opened }))}
                className={clsx(
                  'icon-button-only-gray mr-1 flex h-5 w-5 cursor-pointer items-center justify-center rounded-full',
                  opened ? 'bg-neutral-2' : 'bg-white',
                )}
              >
                <DropDownDown
                  className={clsx('h-4.5 w-4.5 text-gray-50 transition-transform', opened && 'rotate-180')}
                />
              </button>

              {/* 상위 체크박스 */}
              <button
                onClick={() => toggleTask(task)}
                className={clsx(
                  'mr-1.5 grid h-6.5 w-6.5 cursor-pointer place-items-center rounded-full',
                  checked ? 'hover:bg-blue-5' : 'hover:bg-neutral-2',
                )}
              >
                {checked ? (
                  <CheckboxChecked className="relative left-px flex h-4.5 w-4.5" />
                ) : (
                  <CheckboxUnchecked className="text-gray-20 relative left-px h-4.5 w-4.5" />
                )}
              </button>

              <span
                onClick={() => {
                  handleDetailModalOpen('task', task.id);
                }}
                className="text-body-small text-gray-90 cursor-pointer truncate hover:underline"
              >
                {task.title}
              </span>
            </div>

            {/* 하위 업무 */}
            {opened && (
              <div>
                {task.subtasks.map((sub, idx) => {
                  const isLast = idx === task.subtasks.length - 1;
                  const subChecked = checkedMap[task.id].subtasks[sub.id];

                  return (
                    <div
                      key={sub.id}
                      className={clsx(
                        'border-neutral-4 flex h-11.75 items-center border-b',
                        detailModal?.type === 'subtask' &&
                          detailModal.taskId === task.id &&
                          detailModal.subId === sub.id &&
                          'rounded-md2 border-blue-30! bg-blue-1 border',
                      )}
                    >
                      <div className="flex min-w-0 items-center gap-1.5 pr-3 pl-11.5">
                        {isLast ? <LastConnector /> : <Connector />}

                        <button
                          onClick={() => toggleSubTask(task, sub.id)}
                          className={clsx(
                            'mr-1.5 grid h-6.5 w-6.5 cursor-pointer place-items-center rounded-full',
                            subChecked ? 'hover:bg-blue-5' : 'hover:bg-neutral-2',
                          )}
                        >
                          {subChecked ? (
                            <CheckboxChecked className="h-4.5 w-4.5" />
                          ) : (
                            <CheckboxUnchecked className="text-gray-20 h-4.5 w-4.5" />
                          )}
                        </button>

                        <span
                          onClick={() => {
                            handleDetailModalOpen('subtask', task.id, sub.id);
                          }}
                          className="text-body-small text-gray-90 flex-1 cursor-pointer truncate hover:underline"
                        >
                          {sub.title}
                        </span>
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        );
      })}
      {detailModal && (
        <DetailedTaskModal
          onClose={() => setDetailModal(null)}
          data={detailModal}
          tasks={MOCK_TASK}
          checkedMap={checkedMap}
          onToggleCheck={handleCheckToggleFromModal}
          onPrev={goPrev}
          onNext={goNext}
          disablePrev={currentIndex <= 0}
          disableNext={currentIndex >= flatTaskList.length - 1}
        />
      )}
      {showSelectionBar && (
        <SelectionBarModal
          onClose={() => setShowSelectionBar(false)}
          onClearAll={handleClearAll}
          selectedTasks={selectedTasks}
          totalCheckedCount={totalCheckedCount}
          onTaskToggle={handleTaskToggleFromModal}
          onSubtaskToggle={handleSubtaskToggleFromModal}
        />
      )}
    </div>
  );
};

export default DetailedTasksCardComponent;
