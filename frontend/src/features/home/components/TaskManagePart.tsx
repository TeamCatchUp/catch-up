import Depart from '@/public/icons/icon/business_center_filled.svg';
import LoadingProfile from '@/public/icons/icon/loading_profile.svg';
import Manager from '@/public/icons/icon/person_filled.svg';

interface TaskManagePartProps {
  depart: string;
  manager: string;
}

const TaskManagePart = ({ depart, manager }: TaskManagePartProps) => {
  return (
    <div className="flex flex-col">
      <div className="flex flex-col gap-1.25">
        <div className="flex gap-4">
          <div className="flex items-center gap-1.5">
            <Depart className="text-gray-20 h-4 w-4" />
            <span className="text-body-small text-gray-50">담당 부서</span>
          </div>
          <span className="text-body-small text-gray-70">{depart} 팀</span>
        </div>

        <div className="flex gap-7">
          <div className="flex items-center gap-1.5">
            <Manager className="text-gray-20 h-4 w-4" />
            <span className="text-body-small text-gray-50">담당자</span>
          </div>
          <div className="flex items-center gap-2">
            <LoadingProfile className="h-6.25 w-6.25" />
            <span className="text-body-small text-gray-70">{manager}</span>
          </div>
        </div>
      </div>
    </div>
  );
};

export default TaskManagePart;
