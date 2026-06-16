import type { ReactNode } from 'react';

import type { FigmaLabCase } from './types';

interface MetadataSectionProps {
  title: string;
  children: ReactNode;
}

function MetadataSection({ title, children }: MetadataSectionProps) {
  return (
    <section className="border-line-normal-neutral bg-fill-normal-strong flex flex-col gap-2 rounded-lg border p-4">
      <h2 className="text-body-small text-text-normal-normal font-semibold">{title}</h2>
      {children}
    </section>
  );
}

export function FigmaMetadataSection({ activeCase }: { activeCase: FigmaLabCase | undefined }) {
  return (
    <MetadataSection title="Figma">
      {activeCase?.figma ? (
        <dl className="text-body-small text-text-normal-alternative flex flex-col gap-1">
          <div className="flex justify-between gap-3">
            <dt>kind</dt>
            <dd className="text-text-normal-normal">{activeCase.kind}</dd>
          </div>
          <div className="flex justify-between gap-3">
            <dt>group</dt>
            <dd className="text-text-normal-normal">{activeCase.groupId}</dd>
          </div>
          <div className="flex justify-between gap-3">
            <dt>owner</dt>
            <dd className="text-text-normal-normal">{activeCase.owner}</dd>
          </div>
          <div className="flex justify-between gap-3">
            <dt>component</dt>
            <dd className="text-text-normal-normal text-right">{activeCase.component}</dd>
          </div>
          <div className="flex justify-between gap-3">
            <dt>state</dt>
            <dd className="text-text-normal-normal text-right">{activeCase.state}</dd>
          </div>
          {activeCase.usedBy && activeCase.usedBy.length > 0 && (
            <div className="flex justify-between gap-3">
              <dt>usedBy</dt>
              <dd className="text-text-normal-normal text-right">{activeCase.usedBy.join(', ')}</dd>
            </div>
          )}
          <div className="flex justify-between gap-3">
            <dt>fileKey</dt>
            <dd className="text-text-normal-normal break-all">{activeCase.figma.fileKey}</dd>
          </div>
          <div className="flex justify-between gap-3">
            <dt>nodeId</dt>
            <dd className="text-text-normal-normal">{activeCase.figma.nodeId}</dd>
          </div>
          {activeCase.targetRoute && (
            <div className="flex justify-between gap-3">
              <dt>route</dt>
              <dd className="text-text-normal-normal break-all">{activeCase.targetRoute}</dd>
            </div>
          )}
        </dl>
      ) : (
        <p className="text-body-small text-text-normal-alternative">이 case에 등록된 Figma reference가 없습니다.</p>
      )}
    </MetadataSection>
  );
}

export function LayoutMetadataSection({ activeCase }: { activeCase: FigmaLabCase | undefined }) {
  return (
    <MetadataSection title="Layout">
      {activeCase?.layout ? (
        <div className="text-body-small text-text-normal-alternative flex flex-col gap-3">
          <dl className="flex flex-col gap-1">
            {activeCase.layout.shell && (
              <div className="flex justify-between gap-3">
                <dt>shell</dt>
                <dd className="text-text-normal-normal text-right">{activeCase.layout.shell}</dd>
              </div>
            )}
            {activeCase.layout.container && (
              <div className="flex justify-between gap-3">
                <dt>container</dt>
                <dd className="text-text-normal-normal text-right">{activeCase.layout.container}</dd>
              </div>
            )}
            {activeCase.layout.stack && (
              <div className="flex justify-between gap-3">
                <dt>stack</dt>
                <dd className="text-text-normal-normal text-right">{activeCase.layout.stack}</dd>
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
                <span className="text-text-normal-normal font-medium">
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
        <p className="text-body-small text-text-normal-alternative">
          page/section 조립을 검증할 layout contract가 없습니다.
        </p>
      )}
    </MetadataSection>
  );
}

export function DataStateSection({ activeCase }: { activeCase: FigmaLabCase | undefined }) {
  return (
    <MetadataSection title="Data / States">
      {activeCase?.data ? (
        <div className="text-body-small text-text-normal-alternative flex flex-col gap-3">
          <dl className="flex flex-col gap-1">
            <div className="flex justify-between gap-3">
              <dt>source</dt>
              <dd className="text-text-normal-normal">{activeCase.data.source}</dd>
            </div>
            {activeCase.data.api && (
              <div className="flex justify-between gap-3">
                <dt>api</dt>
                <dd className="text-text-normal-normal break-all">{activeCase.data.api}</dd>
              </div>
            )}
          </dl>

          <ul className="flex flex-col gap-1">
            {activeCase.data.fixtures.map((fixture) => (
              <li key={fixture}>{fixture}</li>
            ))}
          </ul>

          <ul className="flex flex-col gap-2">
            {activeCase.data.states.map((item) => (
              <li key={`${item.state}-${item.fixture}`} className="flex flex-col gap-0.5">
                <span className="text-text-normal-normal font-medium">{item.state}</span>
                <span>{item.fixture}</span>
                <span>{item.expected}</span>
                {item.note && <span>{item.note}</span>}
              </li>
            ))}
          </ul>
        </div>
      ) : (
        <p className="text-body-small text-text-normal-alternative">
          fixture와 visual state coverage를 검증할 data/state contract가 없습니다.
        </p>
      )}
    </MetadataSection>
  );
}

export function ComponentReuseSection({ activeCase }: { activeCase: FigmaLabCase | undefined }) {
  return (
    <MetadataSection title="Component reuse">
      {activeCase && activeCase.reuse.length > 0 ? (
        <ul className="text-body-small text-text-normal-alternative flex flex-col gap-2">
          {activeCase.reuse.map((item) => (
            <li key={`${item.figmaPart}-${item.checked}`} className="flex flex-col gap-0.5">
              <span className="text-text-normal-normal font-medium">{item.figmaPart}</span>
              <span>
                {item.decision}: {item.checked}
              </span>
              <span>{item.reason}</span>
            </li>
          ))}
        </ul>
      ) : (
        <p className="text-body-small text-text-normal-alternative">등록된 reuse decision이 없습니다.</p>
      )}
    </MetadataSection>
  );
}

export function DesignTokenSection({ activeCase }: { activeCase: FigmaLabCase | undefined }) {
  return (
    <MetadataSection title="Design tokens">
      {activeCase && activeCase.tokens.length > 0 ? (
        <ul className="text-body-small text-text-normal-alternative flex flex-col gap-2">
          {activeCase.tokens.map((item) => (
            <li key={`${item.figma}-${item.code}`} className="flex flex-col gap-0.5">
              <span className="text-text-normal-normal font-medium">{item.figma}</span>
              <span>
                {item.decision}: {item.code}
              </span>
            </li>
          ))}
        </ul>
      ) : (
        <p className="text-body-small text-text-normal-alternative">등록된 token decision이 없습니다.</p>
      )}
    </MetadataSection>
  );
}
