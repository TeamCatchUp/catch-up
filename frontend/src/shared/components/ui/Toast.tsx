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
          toast: 'bg-alpha-black-75 rounded-xl shadow-modal px-4 py-4 flex items-center justify-center',
          title: 'text-white text-heading-small tracking-tight text-center',
        },
      }}
    />
  );
}
