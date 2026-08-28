'use client';

import { type ExternalToast, toast, Toaster } from 'sonner';

import IconCheckCircleFilled from '@/public/icons/icon/check_circle_filled.svg';
import IconErrorFilled from '@/public/icons/icon/error_filled.svg';

export { type ExternalToast, toast };

export default function Toast() {
  return (
    <Toaster
      position="bottom-center"
      offset={142}
      duration={1000}
      className="z-toast"
      icons={{
        success: <IconCheckCircleFilled aria-hidden className="text-icon-normal-inverse size-6" />,
        error: <IconErrorFilled aria-hidden className="text-icon-normal-inverse size-6" />,
      }}
      toastOptions={{
        unstyled: true,
        classNames: {
          toast:
            'bg-material-alert-modal text-text-normal-inverse rounded-xl shadow-modal px-4 py-4 flex items-center justify-center gap-2',
          content: 'flex flex-col gap-3',
          title: 'text-text-normal-inverse text-heading-small',
          description: 'text-text-normal-inverse text-label-small',
          actionButton:
            'bg-fill-normal-normal text-text-normal-normal border-line-normal-neutral text-body-xsmall h-7.5 shrink-0 rounded-lg border px-2',
        },
      }}
    />
  );
}
