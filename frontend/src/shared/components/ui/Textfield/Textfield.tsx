'use client';

import { Field, Label, Input, Description } from '@headlessui/react';
import clsx from 'clsx';
import { forwardRef } from 'react';
import { TextfieldProps } from './Textfield.types';
import ErrorIcon from '/public/icons/icon/error-1.svg';

const Textfield = forwardRef<HTMLInputElement, TextfieldProps>(
  ({ label, required, helperText, error, suffix, className, ...inputProps }, ref) => {
    const hasError = !!error;

    return (
      <Field className={clsx('flex flex-col gap-1.5', className)}>
        {/* Headline */}
        {label && (
          <Label className="flex items-center gap-1">
            {required && <span className="h-[5px] w-[5px] shrink-0 rounded-full bg-red-50" />}
            <span className="text-heading-medium text-gray-80 tracking-tight">{label}</span>
          </Label>
        )}

        {/* Input field */}
        <div
          className={clsx(
            'flex h-[46px] items-center gap-3 rounded-lg border bg-white p-3',
            hasError
              ? 'border-red-50'
              : 'border-neutral-3 focus-within:border-blue-30',
          )}
        >
          <Input
            ref={ref}
            invalid={hasError}
            className={clsx(
              'text-body-small tracking-tight flex-1 bg-transparent outline-none',
              'text-gray-80 placeholder:text-gray-30',
            )}
            {...inputProps}
          />
          {suffix && <div className="shrink-0">{suffix}</div>}
        </div>

        {/* Helper text / Error message */}
        {error && (
          <div className="flex items-center gap-0.5">
            <ErrorIcon className="h-4 w-4 text-red-50" />
            <Description className="text-label-xsmall tracking-tight text-red-50">{error}</Description>
          </div>
        )}
        {!error && helperText && (
          <Description className="text-label-xsmall tracking-tight text-gray-50">{helperText}</Description>
        )}
      </Field>
    );
  },
);

Textfield.displayName = 'Textfield';

export default Textfield;
