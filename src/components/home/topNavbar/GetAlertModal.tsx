'use client';

import { useState } from 'react';
import ToggleOn from '/public/icons/icon/state=On.svg';
import ToggleOff from '/public/icons/icon/state=Off.svg';

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
    <div
      role="dialog"
      aria-modal="true"
      aria-labelledby="alert-modal-title"
      className="shadow-dropdown-menu border-neutral-4 h-64 w-[281px] rounded-2xl border bg-white px-1.5 py-2"
    >
      <h2 id="alert-modal-title" className="sr-only">
        알림 설정
      </h2>
      <ul>
        {alertItems.map((item) => (
          <li key={item} className="flex items-center justify-between p-2">
            <span className="text-body-small text-gray-80">{item}</span>
            <button
              onClick={() => handleToggle(item)}
              aria-pressed={toggles[item]}
              className="relative bottom-px flex cursor-pointer transition-colors"
            >
              {toggles[item] ? (
                <ToggleOn className="h-6 w-9" aria-hidden="true" />
              ) : (
                <ToggleOff className="h-6 w-9.5" aria-hidden="true" />
              )}
            </button>
          </li>
        ))}
      </ul>
    </div>
  );
};

export default GetAlertModal;
