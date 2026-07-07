'use client';

import type { Meta, StoryObj } from '@storybook/nextjs-vite';
import { expect, within } from 'storybook/test';

import { catchupParameters } from '../../../../../.storybook/catchupStoryParameters';
import SmartFilterInfoTooltip from './SmartFilterInfoTooltip';

const meta = {
  title: 'Compositions/Shared/Query/SmartFilterInfoTooltip',
  component: SmartFilterInfoTooltip,
  tags: ['autodocs'],
  parameters: {
    ...catchupParameters({
      level: 'composition',
      domain: 'shared',
      fsdLayer: 'shared',
      owner: 'shared',
      dataProfile: 'static',
      designSource: 'figma',
      states: ['default', 'tooltip-open'],
      interactionNotes: ['The play function hovers the info icon and verifies tooltip copy.'],
      usedBy: ['home-docs', 'hybrid-search'],
    }),
  },
} satisfies Meta<typeof SmartFilterInfoTooltip>;

export default meta;

type Story = StoryObj<typeof meta>;

export const Default: Story = {
  render: () => (
    <div className="bg-fill-normal-normal flex min-h-20 items-center p-6">
      <SmartFilterInfoTooltip />
    </div>
  ),
  play: async ({ canvasElement, userEvent }) => {
    const canvas = within(canvasElement);
    const portal = within(document.body);

    await userEvent.hover(canvas.getByRole('button', { name: '스마트 필터 설명' }));
    const tooltipCopies = await portal.findAllByText('따로 설정하지 않아도 괜찮아요.');
    await expect(tooltipCopies[0]).toBeInTheDocument();
  },
};
