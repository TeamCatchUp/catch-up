'use client';

import { useState } from 'react';
import AddSmall from '@/assets/icons/icon/add_small.svg';
import IconType from '@/assets/icons/icon/icon_type.svg';
import Error from '@/assets/icons/icon/error.svg';
import Storage from '@/assets/icons/icon/storage.svg';
import CloudCheck from '@/assets/icons/icon/cloud_check.svg';
import Alarm from '@/assets/icons/icon/alarm.svg';
import Rotate from '@/assets/icons/icon/rotate.svg';
import ArrowRight from '@/assets/icons/icon/arrow_right.svg';
import LinkModal from './LinkModal';
import GetAlertModal from './GetAlertModal';

const MoreButtonModal = () => {
  const today = new Date();
  const [selectedButton, setSelectedButton] = useState<string | null>(null);
  const [isLinkModalOpen, setIsLinkModalOpen] = useState(false);
  const [isGetAlertModalOpen, setIsGetAlertModalOpen] = useState(false);

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
      role="dialog"
      aria-modal="true"
      aria-labelledby="more-modal-title"
      className="border-neutral-4 shadow-dropdown-menu flex h-[368px] w-[283px] flex-col gap-3 rounded-2xl border bg-white px-1.5 py-3"
    >
      <section className="border-neutral-3 px-1.5">
        <label htmlFor="more-search" className="sr-only">
          검색어 입력
        </label>
        <input
          id="more-search"
          placeholder="검색어를 입력하세요."
          onFocus={() => {
            setSelectedButton(null);
            setIsLinkModalOpen(false);
            setIsGetAlertModalOpen(false);
          }}
          className="text-body-small placeholder-gray-30 focus:caret-blue-30 focus:bg-neutral-1 focus:border-blue-30 border-neutral-3 h-10 w-[257px] rounded-xl border px-3 py-2 transition-colors outline-none"
        />
      </section>

      <section className="text-body-small text-gray-80 flex flex-col">
        <button
          onClick={() => toggleButton('new')}
          aria-pressed={selectedButton === 'new'}
          className={`flex h-10 cursor-pointer items-center gap-2 rounded-lg p-2 transition-colors ${selectedButton === 'new' ? 'bg-neutral-2' : 'hover:bg-neutral-2'}`}
        >
          <AddSmall className="relative right-px bottom-0.5 h-5 w-5 text-gray-50" />
          <span>새 인수인계 시작하기</span>
        </button>

        <button
          onClick={() => toggleButton('text')}
          aria-pressed={selectedButton === 'text'}
          className={`flex h-10 cursor-pointer justify-between rounded-lg p-2 transition-colors ${selectedButton === 'text' ? 'bg-neutral-2' : 'hover:bg-neutral-2'}`}
        >
          <div className="flex cursor-pointer items-center gap-2">
            <IconType className="relative right-px bottom-0.5 h-5 w-5 text-gray-50" />
            <span>글자 크기</span>
          </div>
          <div className="text-body-xsmall flex cursor-pointer items-center text-gray-50">
            <span>중간</span>
            <ArrowRight className="text-gray-30 h-6 w-6" />
          </div>
        </button>

        <div className="width-[269px] border-neutral-2 my-px border"></div>

        <button
          onClick={() => toggleButton('help')}
          aria-pressed={selectedButton === 'help'}
          className={`flex h-10 cursor-pointer items-center gap-2 rounded-lg p-2 transition-colors ${selectedButton === 'help' ? 'bg-neutral-2' : 'hover:bg-neutral-2'}`}
        >
          <Error className="relative right-0.5 bottom-px h-5.5 w-5.5 text-gray-50" />
          <span className="relative right-0.5">도움말</span>
        </button>

        <button
          onClick={() => toggleButton('version')}
          aria-pressed={selectedButton === 'version'}
          className={`flex h-10 cursor-pointer items-center gap-2 rounded-lg p-2 transition-colors ${selectedButton === 'version' ? 'bg-neutral-2' : 'hover:bg-neutral-2'}`}
        >
          <Storage className="relative right-0.5 bottom-0.5 h-5 w-5 text-gray-50" />
          <span>버전 기록</span>
        </button>

        <div className="width-[269px] border-neutral-2 my-px border"></div>

        <button
          onClick={handleLinkClick}
          aria-pressed={selectedButton === 'link'}
          className={`flex h-10 cursor-pointer justify-between rounded-lg p-2 transition-colors ${selectedButton === 'link' ? 'bg-neutral-2' : 'hover:bg-neutral-2'}`}
        >
          <div className="flex cursor-pointer items-center gap-2">
            <CloudCheck className="relative right-0.5 bottom-0.5 h-5 w-5.5 text-gray-50" />
            <span className="relative right-0.5">연결</span>
          </div>
          <div className="text-body-xsmall flex cursor-pointer items-center text-gray-50">
            <span>Jira</span>
            <ArrowRight className="text-gray-30 h-6 w-6" />
          </div>
        </button>

        <div className="width-[269px] border-neutral-2 my-px border"></div>

        <button
          onClick={handleGetAlertClick}
          aria-pressed={selectedButton === 'alert'}
          className={`flex h-10 cursor-pointer justify-between rounded-lg p-2 transition-colors ${selectedButton === 'alert' ? 'bg-neutral-2' : 'hover:bg-neutral-2'}`}
        >
          <div className="flex cursor-pointer items-center gap-2">
            <Alarm className="relative right-0.5 bottom-0.5 h-5.5 w-5 text-gray-50" />
            <span>알림받기</span>
          </div>
          <div className="text-body-xsmall flex cursor-pointer items-center text-gray-50">
            멘션
            <ArrowRight className="text-gray-30" />
          </div>
        </button>

        <div className="width-[269px] border-neutral-2 my-px border"></div>
      </section>

      <button
        onClick={() => toggleButton('sync')}
        aria-pressed={selectedButton === 'sync'}
        className="text-label-xsmall flex h-10 items-center gap-2 px-2"
      >
        <Rotate className="text-gray-30 relative right-0.5 bottom-0.5 h-5 w-5.5 cursor-pointer" />
        <span className="relative right-0.5 cursor-pointer text-gray-50">
          {today.getFullYear()}년 {today.getMonth() + 1}월 {today.getDate()}일
        </span>
      </button>

      {isLinkModalOpen && (
        <div className="absolute top-[167px] right-[275px]">
          <LinkModal />
        </div>
      )}
      {isGetAlertModalOpen && (
        <div className="absolute top-[167px] right-[275px]">
          <GetAlertModal />
        </div>
      )}
    </div>
  );
};

export default MoreButtonModal;
