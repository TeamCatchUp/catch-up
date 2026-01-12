import clsx from 'clsx';
import { useState } from 'react';
import DropDownDown from '/public/icons/icon/dropdown_down.svg';
import CheckboxUnchecked from '/public/icons/icon/checkbox_unchecked.svg';
import CheckboxChecked from '/public/icons/icon/checkbox_checked.svg';
import Connector from '/public/icons/icon/connector.svg';
import LastConnector from '/public/icons/icon/last_connector.svg';
import DetailedTaskModal from './DetailedTaskModal';

interface SubTask {
  id: number;
  title: string;
}

interface Task {
  id: number;
  title: string;
  subtasks: SubTask[];
}

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
  const [selected, setSelected] = useState<{
    type: 'task' | 'subtask';
    taskId: Number;
    subId?: Number;
  } | null>(null);
  const [isModalOpen, setIsModalOpen] = useState(false);

  // 상위 업무
  const toggleTask = (task: Task) => {
    setCheckedMap((prev) => {
      const current = prev[task.id];
      const nextChecked = !current?.checked;

      //   const subChecked = Object.fromEntries(task.subtasks.map((sub) => [sub.id, nextChecked]));

      //   return {
      //     ...prev,
      //     [task.id]: {
      //       checked: nextChecked,
      //       subtasks: subChecked,
      //     },
      //   };
      return {
        ...prev,
        [task.id]: {
          checked: nextChecked,
          subtasks: Object.fromEntries(task.subtasks.map((sub) => [sub.id, nextChecked])),
        },
      };
    });
  };

  // 하위 업무
  const toggleSubTask = (task: Task, subId: number) => {
    setCheckedMap((prev) => {
      const taskState = prev[task.id];
      if (!taskState) return prev;

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
  };

  //   const handleTaskClick = (taskId: number) => {
  //     setSelected({ type: 'task', taskId });
  //     setIsModalOpen(true);
  //   };
  //   const handleSubTaskClick = (taskId: number, subId: number) => {
  //     setSelected({ type: 'subtask', taskId, subId });
  //     setIsModalOpen(true);
  //   };
  const closeModal = () => {
    setIsModalOpen(false);
    setSelected(null);
  };

  return (
    <div className="flex flex-col">
      {/* 헤더 */}
      <div className="bg-neutral-1 text-body-xsmall flex items-center justify-center rounded-t-2xl rounded-b-md py-1.5 text-gray-50">
        제목
      </div>
      {MOCK_TASK.map((task) => {
        const taskState = checkedMap[task.id];
        const checked = taskState?.checked;
        const opened = openMap[task.id] ?? false;

        return (
          <div key={task.id} className="flex flex-col">
            {/* 상위 업무 */}
            <div
              className={clsx(
                'border-neutral-4 flex items-center border-b px-2 py-3',
                isModalOpen &&
                  selected?.type === 'task' &&
                  selected.taskId === task.id &&
                  'rounded-md2 !border-blue-30 bg-blue-1 border',
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
                  setSelected({ type: 'task', taskId: task.id });
                  setIsModalOpen(true);
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
                  const subChecked = checkedMap[task.id]?.subtasks?.[sub.id] ?? false;

                  return (
                    <div
                      key={sub.id}
                      className={clsx(
                        'border-neutral-4 flex h-11.75 items-center border-b',
                        isModalOpen &&
                          selected?.type === 'subtask' &&
                          selected.taskId === task.id &&
                          selected.subId === sub.id &&
                          'rounded-md2 !border-blue-30 bg-blue-1 border',
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
                            setSelected({ type: 'subtask', taskId: task.id, subId: sub.id });
                            setIsModalOpen(true);
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
      {isModalOpen && <DetailedTaskModal onClose={closeModal} />}
    </div>
  );
};

export default DetailedTasksCardComponent;
