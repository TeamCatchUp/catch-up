'use client';

import type { ComponentProps } from 'react';
import type { Meta, StoryObj } from '@storybook/nextjs-vite';
import { http, HttpResponse } from 'msw';
import { expect, within } from 'storybook/test';

import { API } from '@/shared/api/endpoints';

import { catchupParameters } from '../../../../../.storybook/catchupStoryParameters';
import TopNavbar from './TopNavbar';

type TopNavbarStoryArgs = ComponentProps<typeof TopNavbar>;
type PageType = TopNavbarStoryArgs['pageType'];

const pageTypeOptions: readonly PageType[] = ['home', 'search', 'docs', 'mypage', 'settings'];
const versionHandler = http.get(API.version, () => HttpResponse.text('2026.7.9-local'));

const meta = {
  title: 'Compositions/Shared/Layout/TopNavbar',
  component: TopNavbar,
  tags: ['autodocs'],
  args: {
    pageType: 'home',
  },
  argTypes: {
    pageType: {
      control: 'select',
      options: pageTypeOptions,
    },
  },
  decorators: [
    (Story) => (
      <div className="bg-fill-normal-normal min-h-40">
        <Story />
      </div>
    ),
  ],
  parameters: {
    msw: {
      handlers: [versionHandler],
    },
    ...catchupParameters({
      level: 'composition',
      domain: 'shared',
      fsdLayer: 'shared',
      owner: 'shared',
      dataProfile: 'msw',
      designSource: 'dev-preview',
      viewport: { width: 1440, height: 160 },
      states: ['home', 'search', 'docs', 'mypage', 'settings', 'more-menu'],
      usedBy: ['home-docs', 'agent-studio', 'hybrid-search'],
      dataNotes: ['MSW supplies the app version for the more-menu dropdown.'],
      reuseNotes: ['The app shell and home/search/docs surfaces reuse TopNavbar pageType variants.'],
      interactionNotes: ['The more-menu button opens the help/version dropdown in Storybook.'],
    }),
  },
} satisfies Meta<TopNavbarStoryArgs>;

export default meta;

type Story = StoryObj<TopNavbarStoryArgs>;

export const Home: Story = {
  args: {
    pageType: 'home',
  },
  play: async ({ canvasElement, step, userEvent }) => {
    const canvas = within(canvasElement);
    const portal = within(document.body);

    await step('show the home label', async () => {
      await expect(canvas.getByRole('link', { name: /홈/ })).toBeInTheDocument();
    });

    await step('open more menu with version', async () => {
      await userEvent.click(canvas.getByRole('button', { name: '더보기 메뉴' }));
      await expect(await portal.findByRole('menuitem', { name: '도움말' })).toBeInTheDocument();
      await expect(await portal.findByText('v2026.7.9-local')).toBeInTheDocument();
    });
  },
};

export const Search: Story = {
  args: {
    pageType: 'search',
  },
};

export const Docs: Story = {
  args: {
    pageType: 'docs',
  },
};

export const MyPage: Story = {
  args: {
    pageType: 'mypage',
  },
};

export const Settings: Story = {
  args: {
    pageType: 'settings',
  },
};
