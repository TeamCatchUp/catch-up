import IconCancel from '@/public/icons/icon/cancel.svg';
import IconCheck from '@/public/icons/icon/check.svg';
import { cn } from '@/shared/utils/cn';

import { CONNECTOR_CONTENT } from '../../../constants/connectorContent';
import type { IntegrationService } from '../../../types/integrationModel';

interface ScopeCompareCardProps {
  tone: 'included' | 'excluded';
  title: string;
  items: readonly string[];
}

function ScopeCompareCard({ tone, title, items }: ScopeCompareCardProps) {
  const isIncluded = tone === 'included';
  const Icon = isIncluded ? IconCheck : IconCancel;

  return (
    <div
      className={cn(
        'flex flex-1 flex-col gap-3 rounded-xl p-4',
        isIncluded ? 'bg-accent-green-lighten' : 'bg-accent-red-lighten',
      )}
    >
      <div className="flex items-center gap-4">
        <div className={cn('rounded-lg p-1', isIncluded ? 'bg-accent-green-neutral' : 'bg-accent-red-neutral')}>
          <Icon className="text-icon-normal-normal size-6" />
        </div>
        <h4 className="text-heading-small text-text-normal-strong">{title}</h4>
      </div>

      <ul className="flex flex-col gap-2">
        {items.map((item) => (
          <li key={item} className="flex items-center gap-4">
            <span aria-hidden="true" className="bg-dim-black-25 size-1.5 shrink-0 rounded-full" />
            <span className="text-body-small text-text-normal-normal">{item}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}

interface ConnectorScopeCompareProps {
  service: IntegrationService;
}

/**
 * "연동돼요 / 연동 안 돼요" 대조 카드.
 * Figma `16966:26838` — 카드 padding 16, gap 12, radius 12, 불릿 6px 원.
 */
export default function ConnectorScopeCompare({ service }: ConnectorScopeCompareProps) {
  const { included, excluded } = CONNECTOR_CONTENT[service];

  return (
    <div className="flex gap-5">
      <ScopeCompareCard tone="included" title="연동돼요" items={included} />
      <ScopeCompareCard tone="excluded" title="연동 안 돼요" items={excluded} />
    </div>
  );
}
