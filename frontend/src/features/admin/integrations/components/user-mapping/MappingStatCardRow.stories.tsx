import { useState } from 'react';
import type { Meta, StoryObj } from '@storybook/nextjs-vite';
import { expect, within } from 'storybook/test';

import { catchupParameters } from '../../../../../../.storybook/catchupStoryParameters';
import { CONNECTOR_LOGOS } from '../../constants/connectorLogos';
import MappingStatCardRow, { type MappingStatItem } from './MappingStatCardRow';

const ITEMS: readonly MappingStatItem[] = [
  { key: 'jira', Logo: CONNECTOR_LOGOS.jira, name: 'Jira', percent: 65, countLabel: '65/100' },
  { key: 'github', Logo: CONNECTOR_LOGOS.github, name: 'Github', percent: 65, countLabel: '65/100' },
  { key: 'slack', Logo: CONNECTOR_LOGOS.slack, name: 'Slack', percent: 65, countLabel: '65/100' },
  { key: 'confluence', Logo: CONNECTOR_LOGOS.confluence, name: 'Confluence', percent: 65, countLabel: '65/100' },
  { key: 'channel_talk', Logo: CONNECTOR_LOGOS.channel_talk, name: '채널톡', percent: 65, countLabel: '65/100' },
];

function RowHarness() {
  const [selected, setSelected] = useState<string | null>(null);
  return (
    <MappingStatCardRow
      items={ITEMS}
      selected={selected}
      onToggle={(key) => setSelected((prev) => (prev === key ? null : key))}
    />
  );
}

const meta = {
  title: 'Compositions/Admin/Integrations/User Mapping/MappingStatCardRow',
  component: MappingStatCardRow,
  tags: ['autodocs'],
  parameters: {
    ...catchupParameters({
      level: 'composition',
      domain: 'admin',
      fsdLayer: 'features',
      owner: 'feature',
      dataProfile: 'static',
      designSource: 'figma',
      figma: {
        url: 'https://www.figma.com/design/7UwupbVvmHkElmP2OBJQio/Design-System?node-id=17240-74853',
        fileKey: '7UwupbVvmHkElmP2OBJQio',
        nodeId: '17240:74853',
      },
      viewport: { width: 1100, height: 200 },
      states: ['default', 'toggle'],
      layoutNotes: [
        '카드 p 20, gap 20, 로고칩 48(p 8, radius 12), 이름·완료율 heading-small, 건수 Tag 13px.',
        '카드 208은 행 1040의 5등분 — 폭을 박지 않고 flex-1로 5등분한다.',
      ],
      dataNotes: [
        '통계는 5종(Jira·Confluence 분리), 표 필터는 4종(atlassian 합침) — 매핑은 배선이 정한다.',
        'selected 시각 변형은 Figma에 없어(감사 B-2) aria-pressed만 노출 — 발명 금지.',
      ],
    }),
  },
} satisfies Meta<typeof MappingStatCardRow>;

export default meta;

type Story = StoryObj<typeof MappingStatCardRow>;

export const Default: Story = {
  render: () => (
    <div className="bg-fill-normal-normal w-260 p-4">
      <RowHarness />
    </div>
  ),
  play: async ({ canvasElement, userEvent }) => {
    const canvas = within(canvasElement);

    for (const name of ['Jira', 'Github', 'Slack', 'Confluence', '채널톡']) {
      await expect(canvas.getByText(name)).toBeInTheDocument();
    }
    await expect(canvas.getAllByText('65/100')).toHaveLength(5);

    // 토글 — 같은 카드를 다시 누르면 해제
    const jira = canvas.getByRole('button', { name: /Jira/ });
    await userEvent.click(jira);
    await expect(jira).toHaveAttribute('aria-pressed', 'true');
    await userEvent.click(jira);
    await expect(jira).toHaveAttribute('aria-pressed', 'false');
  },
};
