import type { Meta, StoryObj } from '@storybook/nextjs-vite';
import { expect, fn, within } from 'storybook/test';

import { catchupParameters } from '../../../../../../.storybook/catchupStoryParameters';
import ConnectorSidebarList from './ConnectorSidebarList';

const FIVE = [
  { service: 'jira' as const, workspaceName: '워크스페이스명 text t' },
  { service: 'github' as const, workspaceName: '워크스페이스명 te' },
  { service: 'slack' as const, workspaceName: '워크스페이스명 text' },
  { service: 'confluence' as const, workspaceName: '워크스페이스…' },
  { service: 'channel_talk' as const, workspaceName: '워크스페이스명 tex' },
];

const meta = {
  title: 'Compositions/Admin/Integrations/ConnectorSidebarList',
  component: ConnectorSidebarList,
  tags: ['autodocs'],
  args: { connectors: FIVE, selected: null, onSelect: fn(), onAdd: fn() },
  parameters: {
    ...catchupParameters({
      level: 'composition',
      domain: 'admin',
      fsdLayer: 'features',
      owner: 'feature',
      dataProfile: 'static',
      designSource: 'figma',
      figma: {
        url: 'https://www.figma.com/design/7UwupbVvmHkElmP2OBJQio/Design-System?node-id=17125-115103',
        fileKey: '7UwupbVvmHkElmP2OBJQio',
        nodeId: '17125:115103',
      },
      viewport: { width: 300, height: 400 },
      states: ['add-selected', 'connector-selected', 'single', 'long-workspace-name'],
      reuseNotes: [
        '항목은 설정 사이드바와 같은 SnbMenuItem이다 — Figma에서도 같은 SNB/menu 인스턴스다.',
        '"+ 커넥터 추가하기"와 커넥터 항목 중 정확히 하나만 selected다.',
      ],
    }),
  },
} satisfies Meta<typeof ConnectorSidebarList>;

export default meta;

type Story = StoryObj<typeof ConnectorSidebarList>;

const Frame = ({ children }: { children: React.ReactNode }) => (
  <div className="bg-fill-normal-normal w-65 p-3">{children}</div>
);

/** 아무 커넥터도 고르지 않은 상태 — 추가하기가 선택됨 */
export const AddSelected: Story = {
  render: (args) => (
    <Frame>
      <ConnectorSidebarList {...args} />
    </Frame>
  ),
  play: async ({ canvasElement, userEvent, args }) => {
    const canvas = within(canvasElement);

    await expect(canvas.getByRole('button', { name: '커넥터 추가하기' })).toHaveAttribute('aria-current', 'page');
    await expect(canvas.getByText('연동됨')).toBeInTheDocument();
    await expect(canvas.getByRole('button', { name: /Slack/ })).not.toHaveAttribute('aria-current');

    await userEvent.click(canvas.getByRole('button', { name: /Slack/ }));
    await expect(args.onSelect).toHaveBeenCalledWith('slack');
  },
};

export const ConnectorSelected: Story = {
  args: { selected: 'slack' },
  render: (args) => (
    <Frame>
      <ConnectorSidebarList {...args} />
    </Frame>
  ),
  play: async ({ canvasElement, userEvent, args }) => {
    const canvas = within(canvasElement);

    await expect(canvas.getByRole('button', { name: /Slack/ })).toHaveAttribute('aria-current', 'page');
    await expect(canvas.getByRole('button', { name: '커넥터 추가하기' })).not.toHaveAttribute('aria-current');

    await userEvent.click(canvas.getByRole('button', { name: '커넥터 추가하기' }));
    await expect(args.onAdd).toHaveBeenCalled();
  },
};

export const Single: Story = {
  args: { connectors: [FIVE[2]], selected: 'slack' },
  render: (args) => (
    <Frame>
      <ConnectorSidebarList {...args} />
    </Frame>
  ),
};

export const LongWorkspaceName: Story = {
  args: {
    connectors: [{ service: 'confluence' as const, workspaceName: '아주 긴 워크스페이스명이 들어가면 말줄임 처리가 되는지' }],
  },
  render: (args) => (
    <Frame>
      <ConnectorSidebarList {...args} />
    </Frame>
  ),
};
