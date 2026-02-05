'use client';

import { useState } from 'react';
import IconGithub from '@/public/icons/logo/GitHub.svg';

interface DropdownModalProps {
  onClose: () => void;
  onSelect: (value: string) => void;
}

export default function DropdownModal({ onClose, onSelect }: DropdownModalProps) {
  const [currentSelected, setCurrentSelected] = useState<string | null>(null);

  const options = [
    { id: 'CatchUp_BE_develop_code', label: 'CatchUp_BE', visibility: 'Public' },
    { id: 'DiggIndie_BE_dev_code', label: 'DiggIndie_BE', visibility: 'Public' },
    { id: 'ge_be_develop_code', label: 'ge_be', visibility: 'Public' },
    { id: 'MODELLY_BE_develop_code', label: 'MODELLY_BE', visibility: 'Public' },
    { id: 'STORIX_BE_develop_code', label: 'STORIX_BE', visibility: 'Public' },
  ];

  const selectedRepo = options.find((o) => o.id === currentSelected);

  return (
    <div className="border-gray-5 shadow-dropdown-menu flex h-95 w-62.5 flex-col items-center gap-3 rounded-2xl border bg-white py-2.5">
      <div className="flex flex-col items-start gap-2.5 self-stretch px-2.5">
        <div className="border-blue-30 bg-neutral-1 text-body-small text-blue-55 flex h-10 items-center gap-2.5 self-stretch rounded-lg border px-2.5">
          {selectedRepo ? (
            <>
              <IconGithub className="h-4 w-4" />
              <span className="line-clamp-1">{selectedRepo.label}</span>
            </>
          ) : (
            <span className="text-gray-40">레포지토리를 선택하세요</span>
          )}
        </div>
      </div>

      <div className="flex flex-1 flex-col items-center gap-1 self-stretch overflow-y-auto px-1.5">
        {options.map((option) => (
          <button
            key={option.id}
            onClick={() => {
              setCurrentSelected(option.id);
              onSelect(option.id); // 선택 시 부모에게 전달 및 모달 닫힘
            }}
            className="hover:bg-neutral-1 flex h-10 items-center justify-center gap-2 self-stretch rounded-xl bg-white p-1 transition-colors"
          >
            <div className="rounded-rounded border-neutral-3 bg-neutral-1 flex items-center justify-center gap-2.5 border p-1.5">
              <IconGithub className="h-3.5 w-3.5" />
            </div>
            <div className="text-body-small text-gray-70 line-clamp-1 flex-1 text-left">{option.label}</div>
            <div className="text-nomal-alternative text-body-xsmall text-gray-40 min-w-7.5 pr-1 text-right">
              {option.visibility}
            </div>
          </button>
        ))}
      </div>
    </div>
  );
}
