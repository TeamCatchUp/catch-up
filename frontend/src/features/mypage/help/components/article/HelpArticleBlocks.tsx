import type { ReactNode } from 'react';

import { cn } from '@/shared/utils/cn';

interface HelpArticleSectionProps {
  id: string;
  title: string;
  className?: string;
  titleClassName?: string;
  children: ReactNode;
}

interface HelpArticleSubsectionProps {
  title: string;
  className?: string;
  titleClassName?: string;
  titleVariant?: 'heading-large' | 'reading-large' | 'reading-medium';
  children: ReactNode;
}

interface HelpArticleTextProps {
  children: ReactNode;
  className?: string;
}

interface HelpArticleEmphasisProps {
  children: ReactNode;
  className?: string;
}

interface HelpArticleStepProps {
  order?: number;
  title: string;
  children?: ReactNode;
}

export function HelpArticleText({ children, className }: HelpArticleTextProps) {
  return <div className={cn('text-reading-label-rg-medium text-text-normal-normal', className)}>{children}</div>;
}

export function HelpArticleEmphasis({ children, className }: HelpArticleEmphasisProps) {
  return <span className={cn('text-reading-heading-sb-medium', className)}>{children}</span>;
}

export function HelpArticleSection({ id, title, className, titleClassName, children }: HelpArticleSectionProps) {
  return (
    <section id={id} className={cn('flex scroll-mt-10 flex-col gap-4', className)}>
      <h2 className={cn('text-heading-xlarge text-text-normal-strong', titleClassName)}>{title}</h2>
      {children}
    </section>
  );
}

const helpArticleSubsectionTitleVariants = {
  'heading-large': 'text-heading-large',
  'reading-large': 'text-reading-heading-sb-large',
  'reading-medium': 'text-reading-heading-sb-medium',
} as const;

export function HelpArticleSubsection({
  title,
  className,
  titleClassName,
  titleVariant = 'reading-medium',
  children,
}: HelpArticleSubsectionProps) {
  return (
    <div className={cn('flex flex-col gap-1.5', className)}>
      <h3 className={cn(helpArticleSubsectionTitleVariants[titleVariant], 'text-text-normal-normal', titleClassName)}>
        {title}
      </h3>
      {children}
    </div>
  );
}

export function HelpArticleStep({ order, title, children }: HelpArticleStepProps) {
  return (
    <div className="flex flex-col gap-3">
      {order ? (
        <ol className="text-reading-heading-sb-large text-text-normal-normal list-inside list-decimal" start={order}>
          <li>
            <span>{title}</span>
          </li>
        </ol>
      ) : (
        <h3 className="text-reading-heading-sb-large text-text-normal-normal">{title}</h3>
      )}
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
