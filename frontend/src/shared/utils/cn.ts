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
        'text-reading-heading-sb-large',
        'text-reading-heading-sb-medium',
        'text-reading-heading-sb-small',
        'text-reading-body-md-large',
        'text-reading-body-md-medium',
        'text-reading-body-md-small',
        'text-reading-label-rg-large',
        'text-reading-label-rg-medium',
        'text-reading-label-rg-small',
      ],
    },
  },
});

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}
