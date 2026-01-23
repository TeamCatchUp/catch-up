'use client';

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
              onClick={() =>
                onToggle((prev: any) => ({
                  ...prev,
                  [item]: !prev[item],
                }))
              }
              className="relative bottom-px flex cursor-pointer transition-colors"
            >
              {alerts[item] ? <ToggleOn className="h-6 w-9" /> : <ToggleOff className="h-6 w-9.5" />}
            </button>
          </li>
        ))}
      </ul>
    </div>
  );
};

export default GetAlertModal;
