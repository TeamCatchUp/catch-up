import { useState } from 'react';
import type { Meta, StoryObj } from '@storybook/nextjs-vite';
import { expect, waitFor, within } from 'storybook/test';

import IconBlock from '@/public/icons/icon/block.svg';
import IconBuilding from '@/public/icons/icon/building.svg';
import IconPlugin from '@/public/icons/icon/plugin.svg';

import { catchupParameters } from '../../../../../.storybook/catchupStoryParameters';
import SettingsNavGroup from './SettingsNavGroup';

const CHILDREN = [
  { name: '커넥터 연결', href: '/admin/connectors', Icon: IconPlugin },
  { name: '이용자 매핑', href: '/admin/user-mapping', Icon: IconBlock },
];

const meta = {
  title: 'Compositions/Shared/Layout/SettingsNavGroup',
  component: SettingsNavGroup,
  tags: ['autodocs'],
  args: {
    label: '조직 협업툴 연동',
    Icon: IconBuilding,
    items: CHILDREN,
    activeHref: null,
    onSelect: () => {},
    defaultExpanded: false,
  },
  parameters: {
    ...catchupParameters({
      level: 'composition',
      domain: 'shared',
      fsdLayer: 'shared',
      owner: 'shared',
      dataProfile: 'static',
      designSource: 'figma',
      figma: {
        url: 'https://www.figma.com/design/7UwupbVvmHkElmP2OBJQio/Design-System?node-id=5181-83143',
        fileKey: '7UwupbVvmHkElmP2OBJQio',
        nodeId: '5181:83143',
      },
      viewport: { width: 320, height: 320 },
      states: ['collapsed', 'expanded', 'expanded-child-selected', 'auto-expand-on-route'],
      reuseNotes: ['조직 협업툴 연동과 멤버 관리 두 곳에서 쓴다.'],
      interactionNotes: ['헤더 클릭으로 펼침/접힘이 토글된다.'],
      dataNotes: [
        '마스터 컴포넌트(5181:83143) 기준이다.',
        '설정 화면 네비게이션 인스턴스(17391:94719)는 멤버 관리를 평면으로 그린 구버전이다.',
      ],
    }),
  },
} satisfies Meta<typeof SettingsNavGroup>;

export default meta;

type Story = StoryObj<typeof SettingsNavGroup>;

const Frame = ({ children }: { children: React.ReactNode }) => (
  <div className="bg-fill-normal-normal flex w-60 flex-col p-2">{children}</div>
);

export const Collapsed: Story = {
  render: (args) => (
    <Frame>
      <SettingsNavGroup {...args} />
    </Frame>
  ),
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement);
    await expect(canvas.getByRole('button', { name: /조직 협업툴 연동/ })).toHaveAttribute('aria-expanded', 'false');
    await expect(canvas.queryByRole('button', { name: '커넥터 연결' })).not.toBeInTheDocument();
  },
};

export const Expanded: Story = {
  args: { defaultExpanded: true },
  render: (args) => (
    <Frame>
      <SettingsNavGroup {...args} />
    </Frame>
  ),
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement);
    await expect(canvas.getByRole('button', { name: /조직 협업툴 연동/ })).toHaveAttribute('aria-expanded', 'true');
    await expect(canvas.getByRole('button', { name: '커넥터 연결' })).toBeInTheDocument();
    await expect(canvas.getByRole('button', { name: '이용자 매핑' })).toBeInTheDocument();
  },
};

export const ExpandedChildSelected: Story = {
  args: { defaultExpanded: true, activeHref: '/admin/connectors' },
  render: (args) => (
    <Frame>
      <SettingsNavGroup {...args} />
    </Frame>
  ),
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement);
    await expect(canvas.getByRole('button', { name: '커넥터 연결' })).toHaveAttribute('aria-current', 'page');
    await expect(canvas.getByRole('button', { name: '이용자 매핑' })).not.toHaveAttribute('aria-current');
  },
};

export const TogglesOnHeaderClick: Story = {
  render: (args) => (
    <Frame>
      <SettingsNavGroup {...args} />
    </Frame>
  ),
  play: async ({ canvasElement, userEvent }) => {
    const canvas = within(canvasElement);
    const header = canvas.getByRole('button', { name: /조직 협업툴 연동/ });

    await expect(canvas.queryByRole('button', { name: '커넥터 연결' })).not.toBeInTheDocument();
    await userEvent.click(header);
    await expect(canvas.getByRole('button', { name: '커넥터 연결' })).toBeInTheDocument();
    await userEvent.click(header);
    // 접힘은 퇴장 애니메이션이 끝난 뒤 unmount 된다 — 즉시 단언하면 실패한다
    await waitFor(() => expect(canvas.queryByRole('button', { name: '커넥터 연결' })).not.toBeInTheDocument());
  },
};

/** 그룹 밖 버튼(화면 내 링크 등)으로 하위 경로에 진입하면 접혀 있던 그룹이 스스로 펼쳐진다 */
export const ExpandsWhenChildBecomesActive: Story = {
  render: (args) => {
    const Harness = () => {
      const [activeHref, setActiveHref] = useState<string | null>(null);
      return (
        <Frame>
          <SettingsNavGroup {...args} activeHref={activeHref} onSelect={setActiveHref} defaultExpanded={false} />
          <button type="button" onClick={() => setActiveHref('/admin/user-mapping')}>
            외부 경로 이동
          </button>
        </Frame>
      );
    };
    return <Harness />;
  },
  play: async ({ canvasElement, userEvent }) => {
    const canvas = within(canvasElement);

    await expect(canvas.queryByRole('button', { name: '이용자 매핑' })).not.toBeInTheDocument();

    await userEvent.click(canvas.getByRole('button', { name: '외부 경로 이동' }));
    await waitFor(() =>
      expect(canvas.getByRole('button', { name: '이용자 매핑' })).toHaveAttribute('aria-current', 'page'),
    );
  },
};
