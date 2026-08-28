import IconAiFilled from '@/public/icons/icon/ai_filled.svg';

import type { DocumentPresentationItem, DocumentPresentationRow } from './composeDocumentPresentation';

function DocumentSection({ heading, text }: DocumentPresentationRow) {
  return (
    <article className="m-0 flex flex-col gap-2">
      {heading.length > 0 && <h2 className="text-heading-large text-text-normal-normal m-0">{heading}</h2>}
      {text.length > 0 && <p className="text-body-medium text-text-normal-normal m-0 wrap-break-word break-keep whitespace-pre-wrap">{text}</p>}
    </article>
  );
}

function SummaryCard({ heading, text }: DocumentPresentationRow) {
  return (
    <article className="bg-fill-normal-assistive border-line-normal-neutral m-0 flex flex-col gap-3 rounded-xl border px-5 py-4">
      <div className="flex items-center gap-1.5">
        <IconAiFilled aria-hidden className="text-icon-primary-assistive size-5.5 shrink-0" />
        <h2 className="text-heading-small text-text-primary-assistive m-0 min-w-0">{heading}</h2>
      </div>
      <p className="text-body-medium text-text-normal-normal m-0 wrap-break-word break-keep whitespace-pre-wrap">{text}</p>
    </article>
  );
}

function DetailRows({ rows }: { rows: readonly DocumentPresentationRow[] }) {
  return (
    <dl className="border-line-normal-normal m-0 border-t">
      {rows.map((row) => (
        <div key={row.heading} className="border-line-normal-normal grid grid-cols-[145px_minmax(0,1fr)] border-b">
          <dt className="bg-fill-primary-normal-assistive text-body-medium text-text-normal-normal m-0 flex items-center px-4 py-3 font-semibold">
            {row.heading}
          </dt>
          <dd className="text-body-medium text-text-normal-normal m-0 min-w-0 wrap-break-word break-keep whitespace-pre-wrap px-4 py-3">{row.text}</dd>
        </div>
      ))}
    </dl>
  );
}

function Timeline({ items }: { items: readonly DocumentPresentationRow[] }) {
  return (
    <div className="flex flex-col gap-2">
      {items.map((item, index) => (
        <article key={item.heading} className="m-0 flex min-w-0 gap-5">
          <div className="relative flex w-3 shrink-0 justify-center pt-1.5">
            <span className="bg-fill-normal-interaction-hover size-3 rounded-full" />
            {index < items.length - 1 && <span className="border-line-normal-normal absolute top-7 bottom-0 border-l" />}
          </div>
          <div className="flex min-w-0 flex-1 flex-col gap-3 pb-3">
            <h2 className="text-heading-large text-text-normal-normal m-0">{item.heading}</h2>
            <p className="text-body-medium text-text-normal-normal m-0 wrap-break-word break-keep whitespace-pre-wrap">{item.text}</p>
          </div>
        </article>
      ))}
    </div>
  );
}

export interface DocumentPresentationProps {
  items: readonly DocumentPresentationItem[];
}

export default function DocumentPresentation({ items }: DocumentPresentationProps) {
  return (
    <div className="flex flex-col gap-7">
      {items.map((item, index) => {
        if (item.kind === 'summary') return <SummaryCard key={`${item.kind}-${index}`} heading={item.heading} text={item.text} />;
        if (item.kind === 'details') return <DetailRows key={`${item.kind}-${index}`} rows={item.rows} />;
        if (item.kind === 'timeline') return <Timeline key={`${item.kind}-${index}`} items={item.items} />;
        return <DocumentSection key={`${item.kind}-${index}`} heading={item.heading} text={item.text} />;
      })}
    </div>
  );
}
