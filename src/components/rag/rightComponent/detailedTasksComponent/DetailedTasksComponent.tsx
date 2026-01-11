import clsx from 'clsx';
import { useState } from 'react';
import Align from '/public/icons/icon/align.svg';
import Divider from '/public/icons/icon/divider.svg';
import RagDetailedTasksSkeleton from '@/components/Skeleton/RagDetailedTasksSkeleton';
import DetailedTasksCardComponent from './DetailedTasksCardComponent';

const DetailedTasksComponent = () => {
  const [isLoading, setIsLoading] = useState(false);

  return (
    <div className="flex w-101.25 flex-col gap-3 px-4 py-3">
      <div className="-mb-4 flex w-full overflow-x-auto">
        <div className="flex h-9 min-w-max items-center gap-0.5">
          <button className="icon-button-only-gray flex h-8 w-8 shrink-0 cursor-pointer items-center justify-center rounded-lg p-0.5">
            <Align className="block h-6 w-6 text-gray-50" />
          </button>
          <Divider className="text-neutral-4 block h-6 w-6 shrink-0" />
        </div>
      </div>

      <div className="mt-1 flex flex-col gap-2">
        {isLoading ? <RagDetailedTasksSkeleton /> : <DetailedTasksCardComponent />}
      </div>
    </div>
  );
};

export default DetailedTasksComponent;
