'use client';

import { useEffect } from 'react';
import type { Meta, StoryObj } from '@storybook/nextjs-vite';
import { getRouter } from '@storybook/nextjs-vite/navigation.mock';
import { expect, within } from 'storybook/test';

import { catchupParameters } from '../../../../../.storybook/catchupStoryParameters';
import { useSidebarStore } from '../../../store/sidebarStore';
import SideNavMenu from './SideNavMenu';

type ActivePanel = 'settings' | null;

interface SideNavMenuStoryArgs {
  isOpen: boolean;
  activePanel: ActivePanel;
}

function SideNavMenuSurface({ isOpen, activePanel }: SideNavMenuStoryArgs) {
  useEffect(() => {
    useSidebarStore.setState({
      activePanel,
      lastSettingsPath: '/mypage/profile',
    });
  }, [activePanel]);

  return (
    <div className="bg-background-normal-normal border-line-normal-neutral flex min-h-90 w-60 flex-col border-r p-2">
      <SideNavMenu isOpen={isOpen} />
    </div>
  );
}

const meta = {
  title: 'Compositions/Shared/Layout/SideNavMenu',
  tags: ['autodocs'],
  args: {
    isOpen: true,
    activePanel: null,
  },
  argTypes: {
    isOpen: {
      control: 'boolean',
    },
    activePanel: {
      control: 'inline-radio',
      options: [null, 'settings'],
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
      dataProfile: 'static',
      designSource: 'dev-preview',
      viewport: { width: 320, height: 420 },
      states: ['open', 'collapsed', 'home-active', 'docs-active', 'settings-active', 'agent-active'],
      usedBy: ['home-docs', 'hybrid-search', 'agent-studio'],
      reuseNotes: ['SideNavBar composes SideNavMenu with sidebar open/collapsed state.'],
      interactionNotes: ['Navigation clicks are logged through the Storybook Next navigation mock.'],
    }),
  },
} satisfies Meta<SideNavMenuStoryArgs>;

export default meta;

type Story = StoryObj<SideNavMenuStoryArgs>;

export const HomeActive: Story = {
  render: (args) => <SideNavMenuSurface key={`${args.isOpen}:${args.activePanel}:home`} {...args} />,
  play: async ({ canvasElement, step, userEvent }) => {
    const canvas = within(canvasElement);

    await step('show open navigation labels', async () => {
      await expect(canvas.getByRole('button', { name: /홈/ })).toBeInTheDocument();
      await expect(canvas.getByRole('button', { name: /캐치스턴트 AI/ })).toBeInTheDocument();
      await expect(canvas.getByRole('button', { name: /문서 탐색/ })).toBeInTheDocument();
      await expect(canvas.getByRole('button', { name: /에이전트 스튜디오/ })).toBeInTheDocument();
    });

    await step('route through next navigation mock', async () => {
      const router = getRouter();
      router.push.mockClear();
      await userEvent.click(canvas.getByRole('button', { name: /에이전트 스튜디오/ }));
      await expect(router.push).toHaveBeenCalledWith('/agent-studio');
    });
  },
};

export const DocsActive: Story = {
  parameters: {
    nextjs: {
      navigation: {
        pathname: '/',
        query: {
          mode: 'docs',
        },
      },
    },
  },
  render: (args) => <SideNavMenuSurface key={`${args.isOpen}:${args.activePanel}:docs`} {...args} />,
};

export const SearchActive: Story = {
  parameters: {
    nextjs: {
      navigation: {
        pathname: '/search',
        query: {},
      },
    },
  },
  render: (args) => <SideNavMenuSurface key={`${args.isOpen}:${args.activePanel}:search`} {...args} />,
};

export const SettingsPanelActive: Story = {
  args: {
    activePanel: 'settings',
  },
  parameters: {
    nextjs: {
      navigation: {
        pathname: '/mypage/profile',
        query: {},
      },
    },
  },
  render: (args) => <SideNavMenuSurface key={`${args.isOpen}:${args.activePanel}:settings`} {...args} />,
};

export const AgentStudioActive: Story = {
  parameters: {
    nextjs: {
      navigation: {
        pathname: '/agent-studio/new',
        query: {},
      },
    },
  },
  render: (args) => <SideNavMenuSurface key={`${args.isOpen}:${args.activePanel}:agent`} {...args} />,
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
  render: (args) => <SideNavMenuSurface key={`${args.isOpen}:${args.activePanel}:collapsed`} {...args} />,
};
