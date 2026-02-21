'use client';

import { Toaster } from 'sonner';

export default function Toast() {
  return (
    <Toaster
      position="bottom-center"
      offset={142}
      duration={1000}
      className="z-9999"
      toastOptions={{
        unstyled: true,
        classNames: {
          toast:
            'bg-alpha-black-75 rounded-xl shadow-modal px-4 py-4 flex flex-col items-center justify-center gap-3',
          title: 'text-white text-heading-small tracking-tight text-center',
          description: 'text-white text-label-small tracking-tight text-center',
        },
      }}
    />
  );
}
