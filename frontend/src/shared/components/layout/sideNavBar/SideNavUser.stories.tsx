'use client';

import { useEffect } from 'react';
import type { Meta, StoryObj } from '@storybook/nextjs-vite';
import { expect, within } from 'storybook/test';

import { catchupParameters } from '../../../../../.storybook/catchupStoryParameters';
import { useUserStore } from '../../../store/userStore';
import SideNavUser from './SideNavUser';

interface SideNavUserStoryArgs {
  isOpen: boolean;
  name: string;
  email: string;
  role: 'admin' | 'user';
}

function SideNavUserSurface({ isOpen, name, email, role }: SideNavUserStoryArgs) {
  useEffect(() => {
    useUserStore.setState({
      user: {
        name,
        email,
        role,
        status: 'active',
      },
    });
  }, [email, name, role]);

  return (
    <div className="bg-background-normal-normal border-line-normal-neutral flex min-h-40 w-60 flex-col justify-end border-r p-2">
      <SideNavUser isOpen={isOpen} />
    </div>
  );
}

const meta = {
  title: 'Compositions/Shared/Layout/SideNavUser',
  tags: ['autodocs'],
  args: {
    isOpen: true,
    name: '권보라',
    email: 'user@example.com',
    role: 'admin',
  },
  argTypes: {
    isOpen: {
      control: 'boolean',
    },
    role: {
      control: 'inline-radio',
      options: ['admin', 'user'],
    },
  },
  parameters: {
    nextjs: {
      navigation: {
        pathname: '/',
        query: {},
      },
    },
    ...catchupParameters({
      level: 'composition',
      domain: 'shared',
      fsdLayer: 'shared',
      owner: 'shared',
      dataProfile: 'realistic-fixture',
      designSource: 'dev-preview',
      viewport: { width: 320, height: 240 },
      states: ['open', 'collapsed', 'admin-menu', 'user-menu'],
      usedBy: ['home-docs', 'hybrid-search', 'agent-studio'],
      dataNotes: ['Story wrapper seeds the zustand user store with a realistic signed-in user fixture.'],
      reuseNotes: ['SideNavBar composes SideNavUser at the bottom of the global sidebar.'],
      interactionNotes: ['The user dropdown opens account, preference, permission, theme, help, and logout actions.'],
    }),
  },
} satisfies Meta<SideNavUserStoryArgs>;

export default meta;

type Story = StoryObj<SideNavUserStoryArgs>;

export const AdminOpen: Story = {
  render: (args) => <SideNavUserSurface key={`${args.isOpen}:${args.role}:${args.email}`} {...args} />,
  play: async ({ canvasElement, step, userEvent }) => {
    const canvas = within(canvasElement);
    const portal = within(document.body);

    await step('show user identity', async () => {
      await expect(canvas.getByText('권보라')).toBeInTheDocument();
      await expect(canvas.getByText('user@example.com')).toBeInTheDocument();
    });

    await step('open admin user menu', async () => {
      await userEvent.click(canvas.getByRole('button', { name: /권보라/ }));
      await expect(await portal.findByRole('menuitem', { name: '계정' })).toBeInTheDocument();
      await expect(await portal.findByRole('menuitem', { name: '권한 정보' })).toBeInTheDocument();
    });
  },
};

export const UserOpen: Story = {
  args: {
    name: '이서연',
    email: 'user@example.com',
    role: 'user',
  },
  render: (args) => <SideNavUserSurface key={`${args.isOpen}:${args.role}:${args.email}`} {...args} />,
};

export const Collapsed: Story = {
  args: {
    isOpen: false,
  },
  decorators: [
    (Story) => (
      <div className="w-20">
        <Story />
      </div>
    ),
  ],
  render: (args) => <SideNavUserSurface key={`${args.isOpen}:${args.role}:${args.email}`} {...args} />,
  play: async ({ canvasElement, step }) => {
    const canvas = within(canvasElement);

    await step('expose collapsed user menu button', async () => {
      await expect(canvas.getByRole('button', { name: '사용자 메뉴' })).toBeInTheDocument();
    });
  },
};
