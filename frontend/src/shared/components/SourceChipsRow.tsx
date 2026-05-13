'use client';

// 문서 탐색 모드 입력 박스 아래에 노출되는 소스 chips.
// home·hybrid-search 양쪽에서 재사용. FilterBar와 동일한 SearchOptionButton 사용.

import { useState } from 'react';

import ChannelTalk from '@/public/icons/logo/ChannelTalk.svg';
import Confluence from '@/public/icons/logo/Confluence.svg';
import GitHub from '@/public/icons/logo/GitHub.svg';
import Jira from '@/public/icons/logo/Jira.svg';
import Slack from '@/public/icons/logo/Slack.svg';
import { SearchOptionButton } from '@/shared/components/SearchOptionButton';
import type { DocsSource } from '@/shared/types/source';
import { cn } from '@/shared/utils/cn';

interface SourceItem {
  value: DocsSource;
  label: string;
  Icon: React.FC<React.SVGProps<SVGSVGElement>>;
}

interface SourceChipsRowProps {
  className?: string;
}

const SOURCES: ReadonlyArray<SourceItem> = [
  { value: 'confluence', label: 'Confluence', Icon: Confluence },
  { value: 'jira', label: 'Jira', Icon: Jira },
  { value: 'slack', label: 'Slack', Icon: Slack },
  { value: 'github', label: 'Github', Icon: GitHub },
  { value: 'channel_talk', label: '채널톡', Icon: ChannelTalk },
];

export default function SourceChipsRow({ className }: SourceChipsRowProps) {
  const [selected, setSelected] = useState<DocsSource[]>([]);

  const toggle = (value: DocsSource) => {
    setSelected((prev) => (prev.includes(value) ? prev.filter((v) => v !== value) : [...prev, value]));
  };

  return (
    <div className={cn('flex items-center justify-center gap-2.5', className)}>
      {SOURCES.map((s) => (
        <SearchOptionButton
          key={s.value}
          Icon={s.Icon}
          label={s.label}
          selected={selected.includes(s.value)}
          onClick={() => toggle(s.value)}
        />
      ))}
    </div>
  );
}
