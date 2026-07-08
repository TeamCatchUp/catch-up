'use client';

import type { ReactNode } from 'react';

import type {
  OriginalBlockPayload,
  OriginalButtonPayload,
  OriginalContent,
  OriginalFilePayload,
  OriginalFormPayload,
  OriginalTextPayload,
} from '@/features/hybrid-search/types/originalApi';

export const CHANNEL_TALK_STORY_DOCUMENT_ID = 'channel_talk:user_chat:storybook-fixture';

export function textPayload(content: OriginalContent): OriginalTextPayload {
  if (content.content_type !== 'text') throw new Error('expected text content');
  return content.payload;
}

export function blockPayload(content: OriginalContent): OriginalBlockPayload {
  if (content.content_type !== 'block') throw new Error('expected block content');
  return content.payload;
}

export function buttonPayload(content: OriginalContent): OriginalButtonPayload {
  if (content.content_type !== 'button') throw new Error('expected button content');
  return content.payload;
}

export function formPayload(content: OriginalContent): OriginalFormPayload {
  if (content.content_type !== 'form') throw new Error('expected form content');
  return content.payload;
}

export function filePayload(content: OriginalContent): OriginalFilePayload {
  if (content.content_type !== 'file') throw new Error('expected file content');
  return content.payload;
}

export function StorySurface({ children }: { children: ReactNode }) {
  return <div className="bg-fill-normal-normal flex min-h-full flex-col gap-6 p-6">{children}</div>;
}

export function Case({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div className="flex flex-col gap-1.5">
      <span className="text-body-xsmall text-text-normal-assistive font-medium">{label}</span>
      {children}
    </div>
  );
}

export function PanelWidth({ children }: { children: ReactNode }) {
  return <div className="bg-fill-normal-strong border-line-normal-neutral w-90 rounded-xl border p-3">{children}</div>;
}

export function PanelFrame({ children }: { children: ReactNode }) {
  return (
    <div className="bg-fill-normal-strong border-line-normal-neutral h-160 w-90 overflow-hidden rounded-xl border">
      {children}
    </div>
  );
}

export function SlackPanelWidth({ children }: { children: ReactNode }) {
  return <div className="w-99.75 max-w-full">{children}</div>;
}

export function SlackPanelFrame({ children }: { children: ReactNode }) {
  return (
    <div className="bg-fill-normal-strong border-line-normal-neutral h-160 w-120 overflow-hidden rounded-xl border">
      {children}
    </div>
  );
}
