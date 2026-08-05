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
      states: ['default', 'narrow'],
      layoutNotes: [
        '카드 p 20, gap 20, 로고칩 48(p 8, radius 12), 이름·완료율 heading-small, 건수 Tag 13px.',
        '카드 208은 행 1040의 5등분 — 폭을 박지 않고 flex-1로 5등분한다.',
      ],
      dataNotes: [
        '통계는 5종(Jira·Confluence 분리)이고 표 열은 4종(atlassian 합침) — 표시 전용이라 대응할 필요가 없다.',
        '표시 전용이다 — 눌러도 표는 안 바뀐다(사용자 결정 2026-08-04). Figma 카드는 FRAME 이라 상태 변형 자체가 없다.',
      ],
    }),
  },
} satisfies Meta<typeof MappingStatCardRow>;

export default meta;

type Story = StoryObj<typeof MappingStatCardRow>;

export const Default: Story = {
  args: { items: ITEMS },
  render: (args) => (
    <div className="bg-fill-normal-normal w-260 p-4">
      <MappingStatCardRow {...args} />
    </div>
  ),
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement);

    for (const name of ['Jira', 'Github', 'Slack', 'Confluence', '채널톡']) {
      await expect(canvas.getByText(name)).toBeInTheDocument();
    }
    await expect(canvas.getAllByText('65/100')).toHaveLength(5);

    // 표시 전용 — 누를 수 있는 요소가 없다
    await expect(canvas.queryAllByRole('button')).toHaveLength(0);
  },
};

/** 1024 콘텐츠(656)에서는 5장이 한 줄에 안 들어가 3+2로 접힌다 */
export const Narrow: Story = {
  args: { items: ITEMS },
  render: (args) => (
    <div className="bg-fill-normal-normal w-164 p-4">
      <MappingStatCardRow {...args} />
    </div>
  ),
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement);
    const row = canvas.getByText('Jira').closest('.rounded-xl') as HTMLElement;
    await expect(row.scrollWidth).toBeLessThanOrEqual(row.clientWidth + 1);
  },
};
