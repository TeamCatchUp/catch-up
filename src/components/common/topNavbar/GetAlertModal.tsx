'use client';

import { useState } from 'react';
import ToggleOn from '@/assets/svgs/navbar/toggle_on.svg';
import ToggleOff from '@/assets/svgs/navbar/toggle_off.svg';

const alertItems = ['멘션', '인계자 설정', '인수자 설정', '미팅 1시간 전', '미팅 30분 전', '미팅 시작'];

const GetAlertModal = () => {
  const [toggles, setToggles] = useState(Object.fromEntries(alertItems.map((item, idx) => [item, idx === 0])));

  const handleToggle = (key: string) => {
    setToggles((prev) => ({
      ...prev,
      [key]: !prev[key],
    }));
  };

  return (
    <div className="shadow-dropdown-menu border-neutral-4 h-64 w-[281px] rounded-2xl border bg-white px-1.5 py-2">
      {alertItems.map((item) => (
        <section key={item} className="flex items-center justify-between p-2">
          <span className="text-body-small text-gray-80">{item}</span>
          <button
            onClick={() => handleToggle(item)}
            className="relative bottom-px flex cursor-pointer transition-colors"
          >
            {toggles[item] ? <ToggleOn className="h-6 w-9" /> : <ToggleOff className="h-6 w-9.5" />}
          </button>
        </section>
      ))}
    </div>
  );
};

export default GetAlertModal;
