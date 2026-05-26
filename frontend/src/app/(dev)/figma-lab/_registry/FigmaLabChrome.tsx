import type { ReactNode } from 'react';

import type { FigmaLabCase } from './types';

interface FigmaLabChromeProps {
  activeCase: FigmaLabCase | undefined;
  children: ReactNode;
}

interface MetadataSectionProps {
  title: string;
  children: ReactNode;
}

function MetadataSection({ title, children }: MetadataSectionProps) {
  return (
    <section className="border-edge-neutral bg-fill-strong flex flex-col gap-2 rounded-lg border p-4">
      <h2 className="text-body-small text-content-normal font-semibold">{title}</h2>
      {children}
    </section>
  );
}

export default function FigmaLabChrome({ activeCase, children }: FigmaLabChromeProps) {
  return (
    <div className="mx-auto flex max-w-7xl flex-col gap-6 px-8 py-8">
      <header className="flex flex-col gap-2">
        <p className="text-body-xsmall text-content-assistive font-semibold tracking-wider uppercase">Figma Lab</p>
        <h1 className="text-heading-large text-content-normal font-bold">
          {activeCase?.title ?? '선택된 case가 없습니다'}
        </h1>
        <p className="text-body-medium text-content-alternative">
          Figma 기반 UI 작업을 독립적으로 확인하는 preview surface입니다. 중앙 registry로 case를 추가하고, production
          컴포넌트는 이 route에 의존하지 않게 유지합니다.
        </p>
      </header>

      <div className="grid grid-cols-1 gap-6 xl:grid-cols-[minmax(0,1fr)_360px]">
        <main className="border-edge-neutral bg-fill-normal min-w-0 overflow-auto rounded-lg border p-6">
          {children}
        </main>

        <aside className="flex flex-col gap-4">
          <MetadataSection title="Figma">
            {activeCase?.figma ? (
              <dl className="text-body-small text-content-alternative flex flex-col gap-1">
                <div className="flex justify-between gap-3">
                  <dt>kind</dt>
                  <dd className="text-content-normal">{activeCase.kind}</dd>
                </div>
                <div className="flex justify-between gap-3">
                  <dt>fileKey</dt>
                  <dd className="text-content-normal break-all">{activeCase.figma.fileKey}</dd>
                </div>
                <div className="flex justify-between gap-3">
                  <dt>nodeId</dt>
                  <dd className="text-content-normal">{activeCase.figma.nodeId}</dd>
                </div>
                {activeCase.targetRoute && (
                  <div className="flex justify-between gap-3">
                    <dt>route</dt>
                    <dd className="text-content-normal break-all">{activeCase.targetRoute}</dd>
                  </div>
                )}
              </dl>
            ) : (
              <p className="text-body-small text-content-alternative">이 case에 등록된 Figma reference가 없습니다.</p>
            )}
          </MetadataSection>

          <MetadataSection title="Layout">
            {activeCase?.layout ? (
              <div className="text-body-small text-content-alternative flex flex-col gap-3">
                <dl className="flex flex-col gap-1">
                  {activeCase.layout.shell && (
                    <div className="flex justify-between gap-3">
                      <dt>shell</dt>
                      <dd className="text-content-normal text-right">{activeCase.layout.shell}</dd>
                    </div>
                  )}
                  {activeCase.layout.container && (
                    <div className="flex justify-between gap-3">
                      <dt>container</dt>
                      <dd className="text-content-normal text-right">{activeCase.layout.container}</dd>
                    </div>
                  )}
                  {activeCase.layout.stack && (
                    <div className="flex justify-between gap-3">
                      <dt>stack</dt>
                      <dd className="text-content-normal text-right">{activeCase.layout.stack}</dd>
                    </div>
                  )}
                </dl>

                {activeCase.layout.responsive && activeCase.layout.responsive.length > 0 && (
                  <ul className="flex flex-col gap-1">
                    {activeCase.layout.responsive.map((item) => (
                      <li key={item}>{item}</li>
                    ))}
                  </ul>
                )}

                <ul className="flex flex-col gap-2">
                  {activeCase.layout.relationships.map((item) => (
                    <li key={`${item.from}-${item.to}`} className="flex flex-col gap-0.5">
                      <span className="text-content-normal font-medium">
                        {item.from} → {item.to}
                      </span>
                      <span>
                        {item.figma}: {item.code}
                      </span>
                      {item.note && <span>{item.note}</span>}
                    </li>
                  ))}
                </ul>
              </div>
            ) : (
              <p className="text-body-small text-content-alternative">
                page/section 조립을 검증할 layout contract가 없습니다.
              </p>
            )}
          </MetadataSection>

          <MetadataSection title="Component reuse">
            {activeCase && activeCase.reuse.length > 0 ? (
              <ul className="text-body-small text-content-alternative flex flex-col gap-2">
                {activeCase.reuse.map((item) => (
                  <li key={`${item.figmaPart}-${item.checked}`} className="flex flex-col gap-0.5">
                    <span className="text-content-normal font-medium">{item.figmaPart}</span>
                    <span>
                      {item.decision}: {item.checked}
                    </span>
                    <span>{item.reason}</span>
                  </li>
                ))}
              </ul>
            ) : (
              <p className="text-body-small text-content-alternative">등록된 reuse decision이 없습니다.</p>
            )}
          </MetadataSection>

          <MetadataSection title="Design tokens">
            {activeCase && activeCase.tokens.length > 0 ? (
              <ul className="text-body-small text-content-alternative flex flex-col gap-2">
                {activeCase.tokens.map((item) => (
                  <li key={`${item.figma}-${item.code}`} className="flex flex-col gap-0.5">
                    <span className="text-content-normal font-medium">{item.figma}</span>
                    <span>
                      {item.decision}: {item.code}
                    </span>
                  </li>
                ))}
              </ul>
            ) : (
              <p className="text-body-small text-content-alternative">등록된 token decision이 없습니다.</p>
            )}
          </MetadataSection>
        </aside>
      </div>
    </div>
  );
}
