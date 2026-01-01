'use client';

import { useState } from 'react';
import AddSmall from '@/assets/svgs/navbar/add_small.svg';
import IconType from '@/assets/svgs/navbar/icon_type.svg';
import Error from '@/assets/svgs/navbar/error.svg';
import Storage from '@/assets/svgs/navbar/storage.svg';
import CloudCheck from '@/assets/svgs/navbar/cloud_check.svg';
import Alarm from '@/assets/svgs/navbar/alarm.svg';
import Rotate from '@/assets/svgs/navbar/rotate.svg';
import ArrowRight from '@/assets/svgs/navbar/arrow_right.svg';

const MoreButtonModal = () => {
  const today = new Date();
  const [selectedButton, setSelectedButton] = useState<string | null>(null);

  const toggleButton = (key: string) => {
    setSelectedButton((prev) => (prev === key ? null : key));
  };

  return (
    <div className="border-neutral-4 shadow-dropdown-menu flex h-[368px] w-[283px] flex-col gap-3 rounded-2xl border bg-white px-1.5 py-3">
      <section className="border-neutral-3 px-1.5">
        <input
          placeholder="검색어를 입력하세요."
          className="text-body-small placeholder-gray-30 focus:caret-blue-30 focus:bg-neutral-1 focus:border-blue-30 border-neutral-3 h-10 w-[257px] rounded-xl border px-3 py-2 transition-colors outline-none"
        />
      </section>

      <section className="text-body-small text-gray-80 flex flex-col">
        <button
          onClick={() => toggleButton('new')}
          className={`flex h-10 cursor-pointer items-center gap-2 rounded-lg p-2 transition-colors ${selectedButton === 'new' ? 'bg-neutral-2' : 'hover:bg-neutral-2'}`}
        >
          <AddSmall className="relative right-px bottom-0.5 h-5 w-5 text-gray-50" />
          <p>새 인수인계 시작하기</p>
        </button>

        <div
          onClick={() => toggleButton('text')}
          className={`flex h-10 cursor-pointer justify-between rounded-lg p-2 transition-colors ${selectedButton === 'text' ? 'bg-neutral-2' : 'hover:bg-neutral-2'}`}
        >
          <button className="flex cursor-pointer items-center gap-2">
            <IconType className="relative right-px bottom-0.5 h-5 w-5 text-gray-50" />
            <p>글자 크기</p>
          </button>
          <button className="text-body-xsmall flex cursor-pointer items-center text-gray-50">
            <p>중간</p>
            <ArrowRight className="text-gray-30 h-6 w-6" />
          </button>
        </div>

        <div className="width-[269px] border-neutral-2 border"></div>

        <button
          onClick={() => toggleButton('help')}
          className={`flex h-10 cursor-pointer items-center gap-2 rounded-lg p-2 transition-colors ${selectedButton === 'help' ? 'bg-neutral-2' : 'hover:bg-neutral-2'}`}
        >
          <Error className="relative h-5 w-5 text-gray-50" />
          <p>도움말</p>
        </button>

        <button
          onClick={() => toggleButton('version')}
          className={`flex h-10 cursor-pointer items-center gap-2 rounded-lg p-2 transition-colors ${selectedButton === 'version' ? 'bg-neutral-2' : 'hover:bg-neutral-2'}`}
        >
          <Storage className="relative right-0.5 bottom-0.5 h-5 w-5 text-gray-50" />
          <p>버전 기록</p>
        </button>

        <div className="width-[269px] border-neutral-2 border"></div>

        <div
          onClick={() => toggleButton('link')}
          className={`flex h-10 cursor-pointer justify-between rounded-lg p-2 transition-colors ${selectedButton === 'link' ? 'bg-neutral-2' : 'hover:bg-neutral-2'}`}
        >
          <button className="flex cursor-pointer items-center gap-2">
            <CloudCheck className="relative right-0.5 bottom-0.5 h-5 w-5.5 text-gray-50" />
            <p className="relative right-0.5">연결</p>
          </button>
          <button className="text-body-xsmall flex cursor-pointer items-center text-gray-50">
            <p>Jira</p>
            <ArrowRight className="text-gray-30 h-6 w-6" />
          </button>
        </div>

        <div className="width-[269px] border-neutral-2 border"></div>

        <div
          onClick={() => toggleButton('alert')}
          className={`flex h-10 cursor-pointer justify-between rounded-lg p-2 transition-colors ${selectedButton === 'alert' ? 'bg-neutral-2' : 'hover:bg-neutral-2'}`}
        >
          <button className="flex cursor-pointer items-center gap-2">
            <Alarm className="relative right-0.5 bottom-0.5 h-5.5 w-5 text-gray-50" />
            <p>알림받기</p>
          </button>
          <button className="text-body-xsmall flex cursor-pointer items-center text-gray-50">
            멘션
            <ArrowRight className="text-gray-30" />
          </button>
        </div>

        <div className="width-[269px] border-neutral-2 border"></div>
      </section>

      <button onClick={() => toggleButton('sync')} className="text-label-xsmall flex h-10 items-center gap-2 px-2">
        <Rotate className="text-gray-30 relative right-0.5 bottom-0.5 h-5 w-5.5 cursor-pointer" />
        <p className="relative right-0.5 cursor-pointer text-gray-50">
          {today.getFullYear()}년 {today.getMonth() + 1}월 {today.getDate()}일
        </p>
      </button>
    </div>
  );
};

export default MoreButtonModal;
