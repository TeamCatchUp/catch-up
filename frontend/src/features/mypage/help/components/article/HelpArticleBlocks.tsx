import type { ReactNode } from 'react';

import { cn } from '@/shared/utils/cn';

interface HelpArticleSectionProps {
  id: string;
  title: string;
  titleClassName?: string;
  children: ReactNode;
}

interface HelpArticleSubsectionProps {
  title: string;
  children: ReactNode;
}

interface HelpArticleTextProps {
  children: ReactNode;
  className?: string;
}

interface HelpArticleStepProps {
  order?: number;
  title: string;
  children?: ReactNode;
}

export function HelpDotDivider() {
  return (
    <div className="flex items-center justify-center gap-1.5 py-2">
      <span className="bg-text-normal-assistive size-1 rounded-full" />
      <span className="bg-text-normal-assistive size-1 rounded-full" />
      <span className="bg-text-normal-assistive size-1 rounded-full" />
    </div>
  );
}

export function HelpArticleText({ children, className }: HelpArticleTextProps) {
  return <div className={cn('text-reading-label-rg-medium text-text-normal-normal', className)}>{children}</div>;
}

export function HelpArticleSection({ id, title, titleClassName, children }: HelpArticleSectionProps) {
  return (
    <section id={id} className="flex scroll-mt-10 flex-col gap-4">
      <h2 className={cn('text-heading-xlarge text-text-normal-strong', titleClassName)}>{title}</h2>
      {children}
    </section>
  );
}

export function HelpArticleSubsection({ title, children }: HelpArticleSubsectionProps) {
  return (
    <div className="flex flex-col gap-1.5">
      <h3 className="text-reading-heading-sb-medium text-text-normal-normal">{title}</h3>
      {children}
    </div>
  );
}

export function HelpArticleStep({ order, title, children }: HelpArticleStepProps) {
  return (
    <div className="flex flex-col gap-3">
      <h3 className="text-reading-heading-sb-large text-text-normal-normal">
        {order ? `${order}. ` : ''}
        {title}
      </h3>
      {children}
    </div>
  );
}

export function HelpArticleDisplayHeading({ children }: { children: ReactNode }) {
  return <h2 className="text-display-large text-text-normal-normal">{children}</h2>;
}

export function HelpArticleQuote({ children }: { children: ReactNode }) {
  return (
    <div className="border-line-primary-normal text-reading-label-rg-medium text-text-normal-normal flex w-full border-l-3 px-5">
      {children}
    </div>
  );
}
