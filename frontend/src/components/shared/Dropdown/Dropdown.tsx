'use client';

import {
  Listbox,
  ListboxButton,
  ListboxOptions,
  ListboxOption as HeadlessListboxOption,
} from '@headlessui/react';
import clsx from 'clsx';
import UnfoldMore from '/public/icons/icon/unfold_more.svg';
import { DropdownProps, DropdownOptionProps } from './Dropdown.types';

function Dropdown<T>({
  label,
  required,
  value,
  onChange,
  displayValue,
  placeholder,
  children,
  className,
}: DropdownProps<T>) {
  return (
    <div className={clsx('flex flex-col gap-1.5', className)}>
      {/* Headline */}
      {label && (
        <div className="flex items-center gap-1">
          {required && <span className="h-[5px] w-[5px] shrink-0 rounded-full bg-red-50" />}
          <span className="text-heading-medium text-gray-80 tracking-tight">{label}</span>
        </div>
      )}

      <Listbox value={value} onChange={onChange}>
        {/* 트리거 버튼 */}
        <ListboxButton
          className={clsx(
            'drop-down flex h-[46px] w-full cursor-pointer items-center justify-between px-2.5 py-1.5',
            'data-open:border-neutral-4 data-open:bg-neutral-3',
          )}
        >
          <span
            className={clsx(
              'text-body-small tracking-tight truncate',
              displayValue ? 'text-gray-90' : 'text-gray-30',
            )}
          >
            {displayValue || placeholder}
          </span>
          <UnfoldMore className="h-6 w-6 shrink-0 text-gray-70" />
        </ListboxButton>

        {/* 옵션 목록 */}
        <ListboxOptions
          anchor="bottom start"
          transition
          className={clsx(
            'shadow-dropdown-menu w-(--button-width) rounded-lg bg-white p-1',
            'transition duration-100 ease-out data-closed:opacity-0',
            'z-50',
          )}
        >
          {children}
        </ListboxOptions>
      </Listbox>
    </div>
  );
}

function DropdownOption<T>({ value, children, className }: DropdownOptionProps<T>) {
  return (
    <HeadlessListboxOption
      value={value}
      className={clsx(
        'flex h-10 cursor-pointer items-center rounded-lg px-2 py-2',
        'text-body-small tracking-tight text-gray-80',
        'data-focus:bg-neutral-2 data-selected:bg-neutral-2',
        className,
      )}
    >
      <span className="truncate">{children}</span>
    </HeadlessListboxOption>
  );
}

export { Dropdown, DropdownOption };
