import IconReset from '@/public/icons/icon/reset.svg';
import IconCloseSmall from '@/public/icons/icon/cancel_small.svg';

interface ChipData {
  id: string;
  name: string;
  Icon: any;
  onRemove: () => void;
}

interface SelectedFilterChipsProps {
  chips: ChipData[];
  onReset: () => void;
}

export const SelectedFilterChips = ({ chips, onReset }: SelectedFilterChipsProps) => {
  if (chips.length === 0) return null;

  return (
    <div className="bg-neutral-1 border-neutral-2 mt-2 flex w-full shrink-0 flex-col gap-2 rounded-xl border p-2">
      <div className="flex w-full items-center justify-between px-1 pb-1">
        <div className="text-body-xsmall text-nomal-alternative">선택 항목 {chips.length}</div>
        <button onClick={onReset} className="rounded-rounded bg-neutral-3 flex items-center justify-center p-0.5">
          <IconReset className="h-4.5 w-4.5" />
        </button>
      </div>

      <div className="no-scrollbar flex w-full gap-1.5 overflow-x-auto whitespace-nowrap">
        {chips.map((chip) => {
          const ChipIcon = chip.Icon;
          return (
            <div
              key={chip.id}
              className="border-neutral-5 rounded-rounded flex h-[37px] shrink-0 items-center gap-1 border bg-white p-1.5"
            >
              <div className="rounded-rounded flex h-6.25 w-6.25 shrink-0 items-center justify-center">
                <ChipIcon className="text-blue-10" />
              </div>
              <span className="text-body-small text-gray-80 ml-0.5 max-w-30 truncate">{chip.name}</span>
              <button
                onClick={(e) => {
                  e.stopPropagation();
                  chip.onRemove();
                }}
                className="hover:text-blue-80 ml-0.5 transition-colors"
              >
                <IconCloseSmall className="h-5 w-5" />
              </button>
            </div>
          );
        })}
      </div>
    </div>
  );
};
