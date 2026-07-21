'use client';

import type { Meta, StoryObj } from '@storybook/nextjs-vite';
import { expect, fn, within } from 'storybook/test';

import { catchupParameters } from '../../../../.storybook/catchupStoryParameters';
import { Button } from './button';
import { Popover, PopoverClose, PopoverContent, PopoverTrigger } from './popover';

const alignOptions = ['start', 'center', 'end'] as const;
const sideOptions = ['top', 'right', 'bottom', 'left'] as const;

interface PopoverStoryArgs {
  align: (typeof alignOptions)[number];
  side: (typeof sideOptions)[number];
  onApply: () => void;
}

const meta = {
  title: 'Primitives/Shared/Popover',
  tags: ['autodocs'],
  args: {
    align: 'start',
    side: 'bottom',
    onApply: fn(),
  },
  argTypes: {
    align: {
      control: 'inline-radio',
      options: alignOptions,
    },
    side: {
      control: 'inline-radio',
      options: sideOptions,
    },
    onApply: {
      control: false,
    },
  },
  parameters: {
    ...catchupParameters({
      level: 'primitive',
      domain: 'shared',
      fsdLayer: 'shared',
      owner: 'shared',
      dataProfile: 'static',
      designSource: 'dev-preview',
      states: ['closed', 'open', 'placement'],
      usedBy: ['hybrid-search', 'agent-studio'],
      interactionNotes: ['The play function opens the portal content and clicks an action button.'],
      reuseNotes: ['Primitive popover wrapper used by filters, date pickers, and account selectors.'],
    }),
  },
} satisfies Meta<PopoverStoryArgs>;

export default meta;

type Story = StoryObj<PopoverStoryArgs>;

export const Playground: Story = {
  render: ({ align, side, onApply }) => (
    <div className="bg-fill-normal-normal flex min-h-56 items-start justify-center p-6">
      <Popover>
        <PopoverTrigger asChild>
          <Button variant="box-outline-gray" size="md">
            필터 열기
          </Button>
        </PopoverTrigger>
        <PopoverContent align={align} side={side} className="w-80">
          <div className="flex flex-col gap-3">
            <div className="flex flex-col gap-1">
              <strong className="text-heading-small text-text-normal-strong">문의 상태</strong>
              <span className="text-body-small text-text-normal-alternative">확인할 상태를 선택하세요.</span>
            </div>
            <div className="flex flex-wrap gap-2">
              <Button variant="box-outline-gray" size="sm">
                대기
              </Button>
              <Button variant="box-outline-gray" size="sm">
                진행 중
              </Button>
              <Button variant="box-outline-gray" size="sm">
                완료
              </Button>
            </div>
            <PopoverClose asChild>
              <Button variant="box-solid-primary" size="sm" onClick={onApply}>
                적용
              </Button>
            </PopoverClose>
          </div>
        </PopoverContent>
      </Popover>
    </div>
  ),
  play: async ({ args, canvasElement, step, userEvent }) => {
    const canvas = within(canvasElement);
    const portal = within(document.body);

    await step('open popover', async () => {
      await userEvent.click(canvas.getByRole('button', { name: '필터 열기' }));
      await expect(await portal.findByText('문의 상태')).toBeInTheDocument();
    });

    await step('apply popover action', async () => {
      await userEvent.click(portal.getByRole('button', { name: '적용' }));
      await expect(args.onApply).toHaveBeenCalled();
    });
  },
};

export const OpenState: Story = {
  render: ({ align, side, onApply }) => (
    <div className="bg-fill-normal-normal flex min-h-56 items-start justify-center p-6">
      <Popover defaultOpen>
        <PopoverTrigger asChild>
          <Button variant="box-outline-gray" size="md">
            필터 열기
          </Button>
        </PopoverTrigger>
        <PopoverContent align={align} side={side} className="w-80">
          <div className="flex flex-col gap-3">
            <strong className="text-heading-small text-text-normal-strong">문의 상태</strong>
            <span className="text-body-small text-text-normal-alternative">열린 상태의 popover preview입니다.</span>
            <Button variant="box-solid-primary" size="sm" onClick={onApply}>
              적용
            </Button>
          </div>
        </PopoverContent>
      </Popover>
    </div>
  ),
};
