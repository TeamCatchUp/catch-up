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
            <Depart className="text-content-assistive h-4 w-4" />
            <span className="text-body-small text-content-alternative">담당 부서</span>
          </div>
          <span className="text-body-small text-content-neutral">{depart} 팀</span>
        </div>

        <div className="flex gap-7">
          <div className="flex items-center gap-1.5">
            <Manager className="text-content-assistive h-4 w-4" />
            <span className="text-body-small text-content-alternative">담당자</span>
          </div>
          <div className="flex items-center gap-2">
            <LoadingProfile className="h-6.25 w-6.25" />
            <span className="text-body-small text-content-neutral">{manager}</span>
          </div>
        </div>
      </div>
    </div>
  );
};

export default TaskManagePart;
