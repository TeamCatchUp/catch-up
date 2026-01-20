'use client';

import { useState, useRef } from 'react';
import AddSmall from '/public/icons/icon/add_small.svg';
import IconType from '/public/icons/icon/icon_type.svg';
import Error from '/public/icons/icon/error.svg';
import Storage from '/public/icons/icon/storage.svg';
import CloudCheck from '/public/icons/icon/cloud_check.svg';
import Alarm from '/public/icons/icon/alarm.svg';
import Rotate from '/public/icons/icon/rotate.svg';
import ArrowRight from '/public/icons/icon/arrow_right.svg';
import LinkModal from './LinkModal';
import GetAlertModal from './GetAlertModal';
import { useOutsideClick } from '@/hooks/useOutsideClick';
import { useEscapeKey } from '@/hooks/useEscapeKey';

const linkServices = ['Jira', 'Confluence', 'Github', 'Slack'] as const;
type LinkService = (typeof linkServices)[number];
const alertItems = ['멘션', '인계자 설정', '인수자 설정', '미팅 1시간 전', '미팅 30분 전', '미팅 시작'] as const;
type AlertItem = (typeof alertItems)[number];

const MoreButtonModal = ({ onClose }: { onClose: () => void }) => {
  const modalRef = useRef<HTMLDivElement>(null);
  const today = new Date();

  const [selectedButton, setSelectedButton] = useState<string | null>(null);
  const [isLinkModalOpen, setIsLinkModalOpen] = useState(false);
  const [isGetAlertModalOpen, setIsGetAlertModalOpen] = useState(false);

  const [linked, setLinked] = useState<Record<LinkService, boolean>>({
    Jira: true,
    Confluence: true,
    Github: false,
    Slack: false,
  });
  const [alerts, setAlerts] = useState<Record<AlertItem, boolean>>({
    멘션: true,
    '인계자 설정': true,
    '인수자 설정': false,
    '미팅 1시간 전': false,
    '미팅 30분 전': false,
    '미팅 시작': false,
  });

  useOutsideClick(modalRef, onClose);
  useEscapeKey(onClose);

  const linkedList = linkServices.filter((s) => linked[s]);
  const alertList = alertItems.filter((a) => alerts[a]);

  const toggleButton = (key: string) => {
    if (key === 'link') return handleLinkClick();
    if (key === 'alert') return handleGetAlertClick();

    setIsLinkModalOpen(false);
    setIsGetAlertModalOpen(false);
    setSelectedButton((prev) => (prev === key ? null : key));
  };

  const handleLinkClick = () => {
    if (isLinkModalOpen) {
      setIsLinkModalOpen(false);
      setSelectedButton(null);
    } else {
      setIsLinkModalOpen(true);
      setIsGetAlertModalOpen(false);
      setSelectedButton('link');
    }
  };

  const handleGetAlertClick = () => {
    if (isGetAlertModalOpen) {
      setIsGetAlertModalOpen(false);
      setSelectedButton(null);
    } else {
      setIsGetAlertModalOpen(true);
      setIsLinkModalOpen(false);
      setSelectedButton('alert');
    }
  };

  return (
    <div
      ref={modalRef}
      role="dialog"
      aria-modal="true"
      aria-labelledby="more-modal-title"
      className="border-neutral-4 shadow-dropdown-menu flex h-92 w-63 flex-col gap-3 rounded-2xl border bg-white px-1.5 py-3"
    >
      <section className="border-neutral-3 px-1.5">
        <input
          placeholder="검색어를 입력하세요."
          onFocus={() => {
            setSelectedButton(null);
            setIsLinkModalOpen(false);
            setIsGetAlertModalOpen(false);
          }}
          className="text-body-small placeholder-gray-30 focus:caret-blue-30 focus:bg-neutral-1 focus:border-blue-30 border-neutral-3 h-10 w-57 rounded-xl border px-3 py-2 transition-colors outline-none"
        />
      </section>

      <section className="text-body-small text-gray-80 flex flex-col justify-center">
        <button
          onClick={() => toggleButton('new')}
          aria-pressed={selectedButton === 'new'}
          className={`flex h-10 cursor-pointer items-center rounded-lg p-2 transition-colors ${selectedButton === 'new' ? 'bg-neutral-2' : 'hover:bg-neutral-2'}`}
        >
          <div className="flex items-center justify-center gap-2.5">
            <AddSmall className="h-6 w-6 text-gray-50" />
            <span className="relative top-px">새 인수인계 시작하기</span>
          </div>
        </button>

        <button
          onClick={() => toggleButton('text')}
          aria-pressed={selectedButton === 'text'}
          className={`flex h-10 cursor-pointer justify-between rounded-lg p-2 transition-colors ${selectedButton === 'text' ? 'bg-neutral-2' : 'hover:bg-neutral-2'}`}
        >
          <div className="flex cursor-pointer items-center gap-2.5">
            <IconType className="h-6 w-6 text-gray-50" />
            <span className="relative top-px">글자 크기</span>
          </div>
          <div className="text-body-xsmall flex cursor-pointer items-center text-gray-50">
            <span className="relative top-px">중간</span>
            <ArrowRight className="text-gray-30 h-6 w-6" />
          </div>
        </button>

        <div className="width-[269px] border-neutral-2 my-px border"></div>

        <button
          onClick={() => toggleButton('help')}
          className={`flex h-10 cursor-pointer items-center gap-2.5 rounded-lg p-2 transition-colors ${selectedButton === 'help' ? 'bg-neutral-2' : 'hover:bg-neutral-2'}`}
        >
          <Error className="h-6 w-6 text-gray-50" />
          <span className="">도움말</span>
        </button>

        <button
          onClick={() => toggleButton('version')}
          className={`flex h-10 cursor-pointer items-center gap-2.5 rounded-lg p-2 transition-colors ${selectedButton === 'version' ? 'bg-neutral-2' : 'hover:bg-neutral-2'}`}
        >
          <Storage className="h-6 w-6 text-gray-50" />
          <span>버전 기록</span>
        </button>

        <div className="width-[269px] border-neutral-2 my-px border"></div>

        <button
          onClick={handleLinkClick}
          className={`flex h-10 cursor-pointer justify-between rounded-lg p-2 transition-colors ${selectedButton === 'link' ? 'bg-neutral-2' : 'hover:bg-neutral-2'}`}
        >
          <div className="flex cursor-pointer items-center gap-2.5">
            <CloudCheck className="h-6 w-6 text-gray-50" />
            <span>연결</span>
          </div>
          <div className="text-body-xsmall flex cursor-pointer items-center text-gray-50">
            {linkedList.length > 0 && (
              <span className="relative top-[0.5px] max-w-19.5 truncate">{linkedList.join(', ')}</span>
            )}
            <ArrowRight className="text-gray-30 h-6 w-6" />
          </div>
        </button>

        <div className="width-[269px] border-neutral-2 my-px border"></div>

        <button
          onClick={handleGetAlertClick}
          aria-pressed={selectedButton === 'alert'}
          className={`flex h-10 cursor-pointer justify-between rounded-lg p-2 transition-colors ${selectedButton === 'alert' ? 'bg-neutral-2' : 'hover:bg-neutral-2'}`}
        >
          <div className="flex cursor-pointer items-center gap-2.5">
            <Alarm className="h-6 w-6 text-gray-50" />
            <span>알림받기</span>
          </div>
          <div className="text-body-xsmall flex cursor-pointer items-center text-gray-50">
            {alertList.length > 0 && (
              <span className="relative top-[0.5px] max-w-19.5 truncate">{alertList.join(', ')}</span>
            )}
            <ArrowRight className="text-gray-30 h-6 w-6" />
          </div>
        </button>

        <div className="width-[269px] border-neutral-2 my-px border"></div>
      </section>

      <button onClick={() => toggleButton('sync')} className="text-label-xsmall flex h-10 items-center gap-2.5 px-2">
        <Rotate className="text-gray-30 h-5 w-5 cursor-pointer" />
        <span className="relative top-px flex cursor-pointer items-center text-gray-50">
          {today.getFullYear()}년 {today.getMonth() + 1}월 {today.getDate()}일
        </span>
      </button>

      {isLinkModalOpen && (
        <div className="absolute top-42 right-60">
          <LinkModal linked={linked} onToggle={setLinked} />
        </div>
      )}
      {isGetAlertModalOpen && (
        <div className="absolute top-42 right-60">
          <GetAlertModal alerts={alerts} onToggle={setAlerts} />
        </div>
      )}
    </div>
  );
};

export default MoreButtonModal;
