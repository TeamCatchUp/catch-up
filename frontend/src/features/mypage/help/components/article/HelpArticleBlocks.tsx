import type { ReactNode } from 'react';

interface HelpArticleSectionProps {
  id: string;
  title: string;
  children: ReactNode;
}

interface HelpArticleSubsectionProps {
  title: string;
  children: ReactNode;
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

export function HelpArticleText({ children }: { children: ReactNode }) {
  return <div className="text-reading-label-rg-medium text-text-normal-normal">{children}</div>;
}

export function HelpArticleSection({ id, title, children }: HelpArticleSectionProps) {
  return (
    <section id={id} className="flex scroll-mt-10 flex-col gap-4">
      <h2 className="text-heading-xlarge text-text-normal-strong">{title}</h2>
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
