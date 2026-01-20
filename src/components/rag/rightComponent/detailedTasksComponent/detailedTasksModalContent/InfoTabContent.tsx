import clsx from 'clsx';
import Flag from '/public/icons/icon/flag_filled.svg';
import Menu from '/public/icons/icon/menu.svg';
import UnfoldMore from '/public/icons/icon/unfold_more.svg';
import Status from '/public/icons/icon/status_filled.svg';
import Progress from '/public/icons/icon/progress.svg';
import Person from '/public/icons/icon/person_filled.svg';
import DefaultProfile from '/public/icons/icon/default_profile.svg';
import Divider from '/public/icons/icon/divider.svg';
import Calendar from '/public/icons/icon/calendar_filled.svg';

const InfoTabContent = () => {
  return (
    <div className="flex flex-col gap-2.5">
      {/* 우선순위 */}
      <div className="flex items-center justify-between">
        <div className="flex h-9 items-center gap-2.5">
          <Flag className="text-gray-30 h-4.5 w-4.5" />
          <div className="text-body-small text-gray-50">우선순위:</div>
        </div>
        <button className="box-button-outline-gray flex h-9 w-49.25 cursor-pointer items-center justify-between px-2.5 py-1.5">
          <div className="flex gap-3">
            <Menu className="text-gray-70 h-5 w-5" />
            <span className="text-body-small text-gray-90">높음</span>
          </div>
          <UnfoldMore className="text-gray-30 h-5.5 w-5.5" />
        </button>
      </div>
      {/* 진행상태 */}
      <div className="flex items-center justify-between">
        <div className="flex h-9 items-center gap-2.5">
          <Status className="text-gray-30 relative bottom-px flex h-4.5 w-4.5" />
          <div className="text-body-small text-gray-50">진행 상태:</div>
        </div>
        <button className="box-button-outline-gray flex h-9 w-49.25 cursor-pointer items-center justify-between px-2.5 py-1.5">
          <div className="flex items-center gap-3">
            <Progress className="text-gray-70 h-5 w-5" />
            <span className="text-body-small text-gray-90">진행중</span>
          </div>
          <UnfoldMore className="text-gray-30 h-5.5 w-5.5" />
        </button>
      </div>
      {/* 담당자/담당 조직 */}
      <div className="flex items-center justify-between">
        <div className="flex h-9 items-center gap-2.5">
          <Person className="text-gray-30 h-4.5 w-4.5" />
          <div className="text-body-small text-gray-50">담당자/담당 조직:</div>
        </div>
        <div className="flex h-9 w-49.25 items-center gap-0.5">
          <div className="flex gap-2">
            <DefaultProfile className="h-6.25 w-6.25" />
            <span className="text-body-small text-gray-70 flex items-center">직원04</span>
          </div>
          <Divider className="text-neutral-4 h-6 w-6" />
          <div className="text-body-small text-gray-70">Product</div>
        </div>
      </div>
      {/* 완료 기한 */}
      <div className="flex items-center justify-between">
        <div className="flex h-9 items-center gap-2.5">
          <Calendar className="text-gray-30 h-4.5 w-4.5" />
          <div className="text-body-small text-gray-50">완료 기한:</div>
        </div>
        <div className="text-body-small text-gray-70 flex h-9 w-49.25 items-center text-center">2025.06.02</div>
      </div>
    </div>
  );
};

export default InfoTabContent;
