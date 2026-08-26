'use client';

// 컴포저 아래 템플릿 목록. 2열로 흐르고, 클릭하면 해당 템플릿이 컴포저에 삽입된다.
// 화살표는 hover에서만 나타난다 — 그때 라벨 칸이 그만큼 줄어든다.

import IconArrowOutward from '@/public/icons/icon/arrow_outward.svg';
import IconBugError from '@/public/icons/icon/bug_error.svg';
import IconCopyCheck from '@/public/icons/icon/copy_check.svg';
import IconFolderOpen from '@/public/icons/icon/folder_open.svg';
import IconHistory from '@/public/icons/icon/history.svg';
import IconPerson from '@/public/icons/icon/person2.svg';
import IconSearchFile from '@/public/icons/icon/search_file.svg';

import { tipData } from '../constants/questionTips';

type IconComponent = React.ComponentType<React.SVGProps<SVGSVGElement>>;

// tipData 순서와 1:1로 맞춘다.
const TEMPLATE_ICONS: readonly IconComponent[] = [
  IconPerson,
  IconHistory,
  IconBugError,
  IconCopyCheck,
  IconFolderOpen,
  IconSearchFile,
];

const COLUMNS = 2;

interface QuickTemplateListProps {
  onTemplateClick: (index: number) => void;
}

export default function QuickTemplateList({ onTemplateClick }: QuickTemplateListProps) {
  const rows = Array.from({ length: Math.ceil(tipData.length / COLUMNS) }, (_, row) =>
    tipData.slice(row * COLUMNS, row * COLUMNS + COLUMNS).map((tip, col) => ({ tip, index: row * COLUMNS + col })),
  );

  return (
    <div className="flex w-full flex-col gap-3">
      {rows.map((cells) => (
        <div key={cells[0].index} className="flex gap-6">
          {cells.map(({ tip, index }) => {
            const Icon = TEMPLATE_ICONS[index];
            return (
              <button
                key={tip.title}
                type="button"
                onClick={() => onTemplateClick(index)}
                className="group hover:bg-fill-normal-interaction-hover active:bg-fill-normal-interaction-pressed flex h-10 min-w-0 flex-1 cursor-pointer items-center gap-2 rounded-lg p-2 transition-colors"
              >
                <Icon aria-hidden className="text-icon-normal-neutral size-5 shrink-0" />
                <span className="text-body-small text-text-normal-neutral min-w-0 flex-1 truncate text-left">
                  {tip.title}
                </span>
                <IconArrowOutward
                  aria-hidden
                  className="text-icon-normal-neutral hidden size-5 shrink-0 group-hover:block"
                />
              </button>
            );
          })}
        </div>
      ))}
    </div>
  );
}
