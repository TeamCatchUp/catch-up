import RadioSelectedDot from '@/public/icons/icon/radio_selected_dot.svg';
import RadioSelectedRing from '@/public/icons/icon/radio_selected_ring.svg';
import RadioUnselectedRing from '@/public/icons/icon/radio_unselected_ring.svg';
import { Input } from '@/shared/components/ui/input';

export interface ReasonOption {
  key: string;
  label: string;
}

interface ReasonRadioGroupProps {
  title: string;
  options: ReasonOption[];
  selectedKey: string;
  onSelect: (key: string) => void;
  customValue: string;
  onCustomValueChange: (value: string) => void;
  customPlaceholder?: string;
}

const ReasonRadio = ({
  selected,
  onClick,
  ariaLabel,
}: {
  selected: boolean;
  onClick: () => void;
  ariaLabel: string;
}) => (
  <button
    type="button"
    onClick={onClick}
    aria-label={ariaLabel}
    className="relative mt-px size-6 shrink-0 cursor-pointer"
  >
    <span className="absolute inset-[3px] size-[18px]">
      {selected ? <RadioSelectedRing className="size-[18px]" /> : <RadioUnselectedRing className="size-[18px]" />}
    </span>
    {selected && (
      <span className="absolute inset-[7px] size-[10px]">
        <RadioSelectedDot className="size-[10px]" />
      </span>
    )}
  </button>
);

/** 사유 선택 라디오 그룹 (직접 입력 포함) */
const ReasonRadioGroup = ({
  title,
  options,
  selectedKey,
  onSelect,
  customValue,
  onCustomValueChange,
  customPlaceholder = '반려 사유를 입력해주세요.',
}: ReasonRadioGroupProps) => (
  <div className="mt-4 flex w-full flex-col gap-2">
    <div className="text-body-small text-content-normal flex items-center gap-1">
      {title}
      <span className="block size-[5px] shrink-0 rounded-full bg-red-50" />
    </div>

    <div className="border-edge-assistive flex flex-col gap-4 rounded-xl border px-4 py-4">
      {options.map((option) => {
        if (option.key !== 'custom') {
          return (
            <div key={option.key} className="flex w-full items-center gap-3">
              <ReasonRadio
                selected={selectedKey === option.key}
                onClick={() => onSelect(option.key)}
                ariaLabel={option.label}
              />
              <span className="text-body-small text-content-neutral">{option.label}</span>
            </div>
          );
        }

        const isCustomSelected = selectedKey === 'custom';

        return (
          <div key={option.key} className={`flex w-full gap-3 ${isCustomSelected ? 'items-start' : 'items-center'}`}>
            <ReasonRadio selected={isCustomSelected} onClick={() => onSelect('custom')} ariaLabel={option.label} />
            <div className={`flex min-w-0 flex-1 ${isCustomSelected ? 'flex-col gap-1.5' : 'items-center'}`}>
              <span className="text-body-small text-content-neutral">{option.label}</span>
              {isCustomSelected && (
                <Input
                  inputSize="lg"
                  value={customValue}
                  onChange={(event) => onCustomValueChange(event.target.value)}
                  placeholder={customPlaceholder}
                  className="h-[46px]"
                />
              )}
            </div>
          </div>
        );
      })}
    </div>
  </div>
);

export default ReasonRadioGroup;
