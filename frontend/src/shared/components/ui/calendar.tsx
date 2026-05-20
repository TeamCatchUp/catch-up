'use client';

import { DayPicker, type DayPickerProps } from 'react-day-picker';

import IconArrowLeft from '@/public/icons/icon/arrow_left2.svg';
import IconArrowRight from '@/public/icons/icon/arrow_right2.svg';
import { cn } from '@/shared/utils/cn';

function Calendar({ className, classNames, ...props }: DayPickerProps) {
  return (
    <DayPicker
      className={cn(className)}
      classNames={{
        months: 'relative flex gap-9',
        month: 'flex w-63 flex-col',
        month_caption: 'flex h-9 items-center justify-center pb-2',
        caption_label: 'text-heading-small text-content-normal',
        nav: 'absolute inset-x-0 top-0 z-local flex items-center justify-between',
        button_previous:
          'flex size-7 cursor-pointer items-center justify-center rounded-full text-icon-neutral hover:bg-fill-interaction-hover aria-disabled:cursor-not-allowed aria-disabled:text-icon-assistive aria-disabled:hover:bg-transparent',
        button_next:
          'flex size-7 cursor-pointer items-center justify-center rounded-full text-icon-neutral hover:bg-fill-interaction-hover aria-disabled:cursor-not-allowed aria-disabled:text-icon-assistive aria-disabled:hover:bg-transparent',
        month_grid: 'flex flex-col gap-1',
        weekdays: 'flex',
        weekday: 'flex h-6 flex-1 items-center justify-center text-body-small text-content-alternative',
        weeks: 'flex flex-col gap-1',
        week: 'flex',
        day: 'relative flex h-7 flex-1 items-center justify-center text-body-small text-content-neutral',
        day_button:
          'relative z-base flex size-7 cursor-pointer items-center justify-center rounded-full hover:bg-fill-interaction-hover',
        today: '[&>button]:text-content-primary',
        selected: '',
        // text-white!: react-day-picker 기본 day 색상 specificity를 이기기 위한 important.
        range_start:
          "rdp-range_start [&>button]:bg-fill-primary [&>button]:text-white! [&>button]:hover:bg-fill-primary-interaction-hover before:absolute before:inset-y-0 before:right-0 before:w-1/2 before:bg-fill-interaction-pressed before:content-['']",
        range_end:
          "rdp-range_end [&>button]:bg-fill-primary [&>button]:text-white! [&>button]:hover:bg-fill-primary-interaction-hover before:absolute before:inset-y-0 before:left-0 before:w-1/2 before:bg-fill-interaction-pressed before:content-['']",
        range_middle: 'bg-fill-interaction-pressed',
        outside: '!text-content-assistive',
        disabled: '[&>button]:text-content-assistive [&>button]:hover:bg-transparent [&>button]:cursor-not-allowed',
        hidden: 'invisible',
        ...classNames,
      }}
      components={{
        Chevron: ({ orientation }) =>
          orientation === 'left' ? <IconArrowLeft className="size-5" /> : <IconArrowRight className="size-5" />,
      }}
      fixedWeeks
      {...props}
    />
  );
}

export { Calendar };
