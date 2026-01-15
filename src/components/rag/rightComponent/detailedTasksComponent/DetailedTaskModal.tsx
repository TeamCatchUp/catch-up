import clsx from 'clsx';
import { useState } from 'react';
import DropDownDown from '/public/icons/icon/dropdown_down.svg';
import Kebab from '/public/icons/icon/kebab.svg';
import Cancel from '/public/icons/icon/cancel.svg';
import Check from '/public/icons/icon/check.svg';
import Edit from '/public/icons/icon/edit_square.svg';
import Share from '/public/icons/icon/share_2.svg';
import InfoTabContent from './detailedTasksModalContent/InfoTabContent';
// // Info
// import Flag from '/public/icons/icon/flag_filled.svg';
// import Menu from '/public/icons/icon/menu.svg';
// import UnfoldMore from '/public/icons/icon/unfold_more.svg';
// import Status from '/public/icons/icon/status_filled.svg';
// import Progress from '/public/icons/icon/progress.svg';
// import Person from '/public/icons/icon/person_filled.svg';
// import DefaultProfile from '/public/icons/icon/default_profile.svg';
// import Divider from '/public/icons/icon/divider.svg';
// import Calendar from '/public/icons/icon/calendar_filled.svg';
// 첨부파일
import File from '/public/icons/icon/file.svg';
// 위키
import Wiki from '/public/icons/logo/Wiki.svg';
// url
import Link from '/public/icons/icon/link.svg';
// 댓글
// import DefaultProfile from '/public/icons/icon/default_profile.svg';
import LastConnector from '/public/icons/icon/last_connector.svg';
// import Link from '/public/icons/icon/link.svg';

interface DetailedTaskModalProps {
  onClose: () => void;
  data: {
    type: 'task' | 'subtask';
    taskId: number;
    subId?: Number;
  };
}

type TabType = 'info' | 'files' | 'wiki' | 'url' | 'comments' | 'notion';

const DetailedTaskModal = ({ onClose, data }: DetailedTaskModalProps) => {
  const [activeTab, setActiveTab] = useState<TabType>('info');

  const tabs = [
    { id: 'info' as TabType, label: 'Info', count: 0 },
    { id: 'files' as TabType, label: '첨부파일', count: 2 },
    { id: 'wiki' as TabType, label: 'Wiki', count: 1 },
    { id: 'url' as TabType, label: 'URL', count: 2 },
    { id: 'comments' as TabType, label: '댓글', count: 5 },
    { id: 'notion' as TabType, label: 'Notion', count: 2 },
  ];

  const renderTabContent = () => {
    switch (activeTab) {
      case 'info':
        return <InfoTabContent />;
      case 'files':
        return <div className="p-4">첨부파일 컨텐츠</div>;
      case 'wiki':
        return <div className="p-4">Wiki 컨텐츠</div>;
      case 'url':
        return <div className="p-4">URL 컨텐츠</div>;
      case 'comments':
        return <div className="p-4">댓글 컨텐츠</div>;
      case 'notion':
        return <div className="p-4">Notion 컨텐츠</div>;
      default:
        return null;
    }
  };

  return (
    <div className="shadow-rag-bar border-neutral-4 absolute bottom-4 ml-8 flex h-145 w-108.75 flex-col rounded-2xl border bg-white p-5">
      {/* TopMenuBar */}
      <div className="flex justify-between">
        <div className="flex gap-1.5">
          <button className="rounded-md2! box-button-outline-gray h-7.5 w-7.5 cursor-pointer p-1">
            <DropDownDown className="h-5 w-5 rotate-180" />
          </button>
          <button className="rounded-md2! box-button-outline-gray h-7.5 w-7.5 cursor-pointer p-1">
            <DropDownDown className="h-5 w-5" />
          </button>
        </div>
        <div className="-mr-px flex items-center justify-center gap-1.5">
          <button className="icon-button-only-gray flex h-7 w-7 cursor-pointer items-center justify-center rounded-full! p-0.5">
            <Kebab className="h-5 w-5 text-gray-50" />
          </button>
          <button className="icon-button-only-gray flex h-7 w-7 cursor-pointer items-center justify-center rounded-full! p-0.5">
            <Cancel className="h-5 w-5 text-gray-50" />
          </button>
        </div>
      </div>
      {/* title */}
      <div className="mt-4 flex max-h-14.5 items-center gap-2.5">
        <button className="border-neutral-3 bg-neutral-1 flex h-8.5 w-8.5 cursor-pointer items-center justify-center rounded-lg border p-1.5">
          <Check className="text-gray-30 h-5.5 w-5.5" />
        </button>
        <span className="text-heading-large text-gray-70 line-clamp-2">
          국내 주요 고객사(Top 5) 사용 패턴 분석 및 개선 포인트 도출
        </span>
      </div>
      {/* option bar */}
      <div className="mt-3.5 flex h-15 gap-5 overflow-x-auto">
        {tabs.map((tab) => (
          <button
            key={tab.id}
            onClick={() => setActiveTab(tab.id)}
            className={clsx('relative flex shrink-0 cursor-pointer items-center justify-center gap-1.5')}
          >
            <span
              className={clsx('text-heading-small relative', activeTab === tab.id ? 'text-blue-55' : 'text-gray-50')}
            >
              {tab.label}
            </span>
            {tab.count > 0 && (
              <span
                className={clsx(
                  'text-body-xsmall rounded-md2 flex h-5 w-5 items-center justify-center text-center',
                  activeTab === tab.id ? 'bg-blue-50 text-white' : 'bg-neutral-3 text-gray-50',
                )}
              >
                {tab.count}
              </span>
            )}
            {activeTab === tab.id && (
              <div className="bg-blue-45 absolute right-0 bottom-1.75 left-0 z-50 h-0.5 translate-y-1.5" />
            )}
          </button>
        ))}
      </div>
      <span className="bg-neutral-3 relative bottom-2.75 flex h-px" />

      <div className="mt-4 flex h-100 flex-col overflow-y-auto">
        {/* content */}
        {renderTabContent()}

        {/* divider */}
        <div className="mt-6 flex flex-col gap-4">
          <div className="border-neutral-3 flex border" />
          {/* 상위 업무 */}
          <div className="flex gap-1.5">
            <button className="cursor-pointer">
              <DropDownDown className="text-gray-70 h-4.5 w-4.5" />
            </button>
            <span className="text-heading-small text-gray-80">상위 업무</span>
            <span className="text-heading-small text-blue-40">1</span>
          </div>
          <div className="text-body-small text-gray-70 flex w-98 flex-wrap gap-x-3 gap-y-2.5">
            <span className="capsule-button-outline-purple px-3 py-1.5">일본 파트너사 콜드메일 제목 수정안 검토</span>
            <span className="capsule-button-outline-purple px-3 py-1.5">일본 파트너사 콜</span>
            <span className="capsule-button-outline-light-blue px-3 py-1.5">
              일본 파트너사 콜드메일 제목 수정안 검토
            </span>
          </div>
        </div>
      </div>
      {/* 기능 버튼 */}
      <div className="mt-3 flex h-9 items-center justify-between gap-4">
        <button className="capsule-button-outline-blue flex w-48 cursor-pointer items-center justify-center gap-1.5 px-3 py-1.5">
          <div className="relative top-px flex h-5 w-5 items-center">
            <Edit className="text-blue-50" />
          </div>
          <span className="text-blue-55 text-body-small">인수인계 시작하기</span>
        </button>
        <button className="capsule-button-solid-primary flex w-48 cursor-pointer items-center justify-center gap-1.5 px-3 py-1.5">
          <div className="relative top-px flex h-5 w-5 items-center">
            <Share className="" />
          </div>
          <span className="text-body-small">자료 공유하기</span>
        </button>
      </div>
    </div>
  );
};

export default DetailedTaskModal;
