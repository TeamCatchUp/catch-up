'use client';

import { useEffect } from 'react';
import type { Meta, StoryObj } from '@storybook/nextjs-vite';
import { expect, within } from 'storybook/test';

import type { UserRole } from '@/shared/queries/auth.types';

import { catchupParameters } from '../../../../../.storybook/catchupStoryParameters';
import { useUserStore } from '../../../store/userStore';
import SettingsPanel from './SettingsPanel';

interface SettingsPanelStoryArgs {
  role: UserRole;
}

function SettingsPanelSurface({ role }: SettingsPanelStoryArgs) {
  useEffect(() => {
    useUserStore.setState({
      user: { name: '김캐치', email: 'catch@example.com', role, status: 'active' },
    });
  }, [role]);

  return <SettingsPanel />;
}

const meta = {
  title: 'Compositions/Shared/Layout/Settings/SettingsPanel',
  tags: ['autodocs'],
  args: { role: 'admin' },
  argTypes: {
    role: { control: 'inline-radio', options: ['admin', 'user'] },
  },
  parameters: {
    nextjs: {
      navigation: { pathname: '/admin/connectors', query: {} },
    },
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
      viewport: { width: 320, height: 900 },
      states: ['root-admin', 'member'],
      dataNotes: [
        'Figma 마스터 Settings SNB(5181:83143 루트어드민 / 5851:72323 팀원) 기준.',
        'Catch Up MCP 메뉴는 라우트가 없어 제외했다.',
        '팀원 메뉴도 "채팅 히스토리"로 통일한다 — Figma는 "질문 히스토리"로 그렸다.',
      ],
    }),
  },
} satisfies Meta<SettingsPanelStoryArgs>;

export default meta;

type Story = StoryObj<SettingsPanelStoryArgs>;

export const RootAdmin: Story = {
  render: (args) => <SettingsPanelSurface key={args.role} {...args} />,
  play: async ({ canvasElement, userEvent }) => {
    const canvas = within(canvasElement);

    // Chromatic 캡처 환경은 로컬보다 렌더가 늦을 수 있다 — 존재 단언은 재시도형 findByRole로
    await expect(await canvas.findByRole('button', { name: /메인으로 가기/ })).toBeInTheDocument();
    await expect(await canvas.findByRole('button', { name: /조직 협업툴 연동/ })).toBeInTheDocument();
    await expect(await canvas.findByRole('button', { name: /멤버 관리/ })).toBeInTheDocument();

    // 감사 로그는 폐기됐다
    await expect(canvas.queryByRole('button', { name: /감사 로그/ })).not.toBeInTheDocument();
    // Catch Up MCP는 라우트가 없어 넣지 않았다
    await expect(canvas.queryByRole('button', { name: /Catch Up MCP/ })).not.toBeInTheDocument();

    // 활성 경로가 /admin/connectors 이므로 협업툴 연동 그룹은 펼쳐진 채 시작한다
    await expect(await canvas.findByRole('button', { name: '커넥터 연결' })).toHaveAttribute('aria-current', 'page');

    // 멤버 관리는 접혀 있다가 클릭하면 펼쳐진다
    await expect(canvas.queryByRole('button', { name: '멤버 채팅 기록' })).not.toBeInTheDocument();
    await userEvent.click(canvas.getByRole('button', { name: /멤버 관리/ }));
    await expect(await canvas.findByRole('button', { name: '멤버 정보' })).toBeInTheDocument();
    await expect(await canvas.findByRole('button', { name: '멤버 채팅 기록' })).toBeInTheDocument();
  },
};

export const Member: Story = {
  args: { role: 'user' },
  parameters: {
    nextjs: {
      navigation: { pathname: '/mypage/history', query: {} },
    },
  },
  render: (args) => <SettingsPanelSurface key={args.role} {...args} />,
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement);

    // 팀원도 "채팅 히스토리"로 통일한다
    await expect(canvas.getByRole('button', { name: '채팅 히스토리' })).toHaveAttribute('aria-current', 'page');
    await expect(canvas.queryByRole('button', { name: '질문 히스토리' })).not.toBeInTheDocument();

    // 조직 관리 섹션은 팀원에게 없다
    await expect(canvas.queryByRole('button', { name: /조직 협업툴 연동/ })).not.toBeInTheDocument();
    await expect(canvas.queryByRole('button', { name: /멤버 관리/ })).not.toBeInTheDocument();
  },
};
