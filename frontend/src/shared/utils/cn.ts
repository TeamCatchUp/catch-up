import { type ClassValue, clsx } from 'clsx';
import { extendTailwindMerge } from 'tailwind-merge';

const twMerge = extendTailwindMerge({
  extend: {
    classGroups: {
      'font-size': [
        'text-display-xlarge',
        'text-display-large',
        'text-heading-xlarge',
        'text-heading-large',
        'text-heading-medium',
        'text-heading-small',
        'text-body-large',
        'text-body-medium',
        'text-body-small',
        'text-body-xsmall',
        'text-label-large',
        'text-label-medium',
        'text-label-small',
        'text-label-xsmall',
      ],
    },
  },
});

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}
