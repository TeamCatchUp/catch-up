'use client';

import * as React from 'react';
import { DayPicker, type DayPickerProps } from 'react-day-picker';

import IconArrowLeft from '@/public/icons/icon/arrow_left.svg';
import IconArrowRight from '@/public/icons/icon/arrow_right.svg';
import { cn } from '@/shared/utils/cn';

function Calendar({ className, classNames, ...props }: DayPickerProps) {
  return (
    <DayPicker
      className={cn('p-5', className)}
      classNames={{
        months: 'relative flex gap-9',
        month: 'flex w-[220px] flex-col',
        month_caption: 'flex h-[34px] items-center justify-center pb-1.5',
        caption_label: 'text-body-small text-content-strong',
        nav: 'absolute inset-x-0 top-0 z-20 flex items-center justify-between',
        button_previous:
          'flex size-7 cursor-pointer items-center justify-center rounded-full text-icon-neutral hover:bg-fill-interaction-hover',
        button_next:
          'flex size-7 cursor-pointer items-center justify-center rounded-full text-icon-neutral hover:bg-fill-interaction-hover',
        weekdays: 'flex',
        weekday: 'flex h-6 flex-1 items-center justify-center text-label-xsmall text-content-alternative',
        week: 'flex',
        day: 'relative flex h-6 flex-1 items-center justify-center text-label-xsmall text-content-neutral',
        day_button:
          'relative z-10 flex size-6 cursor-pointer items-center justify-center rounded-full hover:bg-fill-interaction-hover',
        today: '',
        selected: '',
        range_start:
          "rdp-range_start [&>button]:bg-fill-primary [&>button]:text-white [&>button]:hover:bg-fill-primary before:absolute before:inset-y-0 before:right-0 before:w-1/2 before:bg-fill-interaction-pressed before:content-['']",
        range_end:
          "rdp-range_end [&>button]:bg-fill-primary [&>button]:text-white [&>button]:hover:bg-fill-primary before:absolute before:inset-y-0 before:left-0 before:w-1/2 before:bg-fill-interaction-pressed before:content-['']",
        range_middle: 'bg-fill-interaction-pressed',
        outside: 'text-content-assistive',
        disabled: 'text-content-assistive opacity-50',
        hidden: 'invisible',
        ...classNames,
      }}
      components={{
        Chevron: ({ orientation }) =>
          orientation === 'left' ? <IconArrowLeft className="size-5" /> : <IconArrowRight className="size-5" />,
      }}
      {...props}
    />
  );
}

export { Calendar };
