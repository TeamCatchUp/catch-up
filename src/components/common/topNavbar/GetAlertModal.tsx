'use client';

import clsx from 'clsx';
import ToggleOn from '/public/icons/icon/state=On.svg';
import ToggleOff from '/public/icons/icon/state=Off.svg';

type Props = {
  alerts: Record<string, boolean>;
  onToggle: React.Dispatch<React.SetStateAction<any>>;
};

const GetAlertModal = ({ alerts, onToggle }: Props) => {
  return (
    <div className="shadow-dropdown-menu border-neutral-4 h-64 w-63 rounded-2xl border bg-white px-1.5 py-2">
      <ul>
        {Object.keys(alerts).map((item) => (
          <li key={item} className="flex items-center justify-between p-2">
            <span className="text-body-small text-gray-80">{item}</span>
            <button
              onMouseDown={(e) => {
                e.stopPropagation();
                (e.nativeEvent as any).stopImmediatePropagation?.();
              }}
              onClick={(e) => {
                e.stopPropagation();
                (e.nativeEvent as any).stopImmediatePropagation?.();

                onToggle((prev: any) => ({
                  ...prev,
                  [item]: !prev[item],
                }));
              }}
              className="relative bottom-px flex cursor-pointer transition-colors"
            >
              {alerts[item] ? <ToggleOn className="h-6 w-9" /> : <ToggleOff className="h-6 w-9.5" />}
              {/* className={clsx(
                'relative h-6 w-10 cursor-pointer rounded-full transition-colors duration-200 ease-out',
                alerts[item] ? 'bg-blue-50' : 'bg-neutral-3',
              )}
            >
              <span
                className={clsx(
                  'absolute top-0.5 left-0.5 h-5 w-5 rounded-full bg-white shadow-sm',
                  'transition-transform duration-200 ease-out will-change-transform',
                  alerts[item] ? 'translate-x-4' : 'translate-x-0',
                )}
              /> */}
            </button>
          </li>
        ))}
      </ul>
    </div>
  );
};

export default GetAlertModal;
