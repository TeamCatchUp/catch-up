'use client';

import { useState } from 'react';
import Align from '/public/icons/icon/align.svg';
import Divider from '/public/icons/icon/divider.svg';
import Person from '/public/icons/icon/person.svg';
import Tag from '/public/icons/icon/tag.svg';
import Space from '/public/icons/icon/space.svg';
import ArrowRight from '/public/icons/icon/arrow_right2.svg';
import RagDetailedTasksSkeleton from '@/components/Skeleton/RagRightComponentSkeleton';
import TaskCard from './TaskCard';
import { SearchOptionButton } from '@/shared/components/SearchOptionButton';

const searchOptions = [
  {
    key: 'person',
    label: '담당자',
    Icon: Person,
  },
  {
    key: 'tag',
    label: '부서명',
    Icon: Tag,
  },
  {
    key: 'space',
    label: '프로젝트',
    Icon: Space,
  },
];

interface TaskListProps {
  tasks: JiraTask[];
  isLoading?: boolean;
}

const TaskList = ({ tasks, isLoading }: TaskListProps) => {
  const [selectedOptions, setSelectedOptions] = useState<Set<string>>(new Set());

  const toggleOption = (key: string) => {
    setSelectedOptions((prev) => {
      const next = new Set(prev);
      if (next.has(key)) {
        next.delete(key);
      } else {
        next.add(key);
      }
      return next;
    });
  };

  return (
    <div className="flex w-full flex-col gap-3 px-4 py-3">
      <div className="flex w-full overflow-x-auto">
        <div className="flex h-9 min-w-max items-center gap-0.5">
          <button className="icon-button-only-gray flex h-8 w-8 shrink-0 cursor-pointer items-center justify-center rounded-lg p-0.5">
            <Align className="block h-6 w-6 text-gray-50" />
          </button>
          <Divider className="text-neutral-4 mr-1 block h-6 w-6 shrink-0" />
        </div>

        <div className="flex items-center gap-2.5">
          {searchOptions.map(({ key, label, Icon }) => {
            return (
              <SearchOptionButton
                key={key}
                Icon={Icon}
                label={label}
                selected={selectedOptions.has(key)}
                onClick={() => toggleOption(key)}
              />
            );
          })}
          <button className="icon-button-only-gray flex h-6.5 w-6.5 cursor-pointer items-center justify-center rounded-full!">
            <ArrowRight className="h-5 w-5 text-gray-50" />
          </button>
        </div>
      </div>

      <div className="flex flex-col gap-2">
        {isLoading ? (
          <RagDetailedTasksSkeleton message={'관련 상세 업무를 분석하는 중입니다.'} />
        ) : (
          <TaskCard tasks={tasks} />
        )}
      </div>
    </div>
  );
};

export default TaskList;
