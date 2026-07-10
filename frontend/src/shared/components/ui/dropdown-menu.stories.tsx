'use client';

import type { Meta, StoryObj } from '@storybook/nextjs-vite';
import { expect, fn, within } from 'storybook/test';

import MoreIcon from '@/public/icons/icon/kebab.svg';

import { catchupParameters } from '../../../../.storybook/catchupStoryParameters';
import { Button } from './button';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from './dropdown-menu';

interface DropdownMenuStoryArgs {
  align: 'start' | 'center' | 'end';
  disabledArchive: boolean;
  onDuplicate: () => void;
  onArchive: () => void;
  onDelete: () => void;
}

const alignOptions = ['start', 'center', 'end'] as const;

const meta = {
  title: 'Primitives/Shared/DropdownMenu',
  tags: ['autodocs'],
  args: {
    align: 'end',
    disabledArchive: false,
    onDuplicate: fn(),
    onArchive: fn(),
    onDelete: fn(),
  },
  argTypes: {
    align: {
      control: 'inline-radio',
      options: alignOptions,
    },
    disabledArchive: {
      control: 'boolean',
    },
    onDuplicate: {
      control: false,
    },
    onArchive: {
      control: false,
    },
    onDelete: {
      control: false,
    },
  },
  render: ({ align, disabledArchive, onDuplicate, onArchive, onDelete }) => (
    <div className="bg-fill-normal-normal flex min-h-40 items-start justify-center p-6">
      <DropdownMenu>
        <DropdownMenuTrigger asChild>
          <Button variant="icon-outline-gray" size="sm" aria-label="에이전트 메뉴">
            <MoreIcon className="size-5" aria-hidden="true" />
          </Button>
        </DropdownMenuTrigger>
        <DropdownMenuContent align={align}>
          <DropdownMenuLabel>에이전트 작업</DropdownMenuLabel>
          <DropdownMenuSeparator />
          <DropdownMenuItem onSelect={onDuplicate}>복제하기</DropdownMenuItem>
          <DropdownMenuItem disabled={disabledArchive} onSelect={onArchive}>
            보관하기
          </DropdownMenuItem>
          <DropdownMenuSeparator />
          <DropdownMenuItem onSelect={onDelete}>삭제하기</DropdownMenuItem>
        </DropdownMenuContent>
      </DropdownMenu>
    </div>
  ),
  parameters: {
    ...catchupParameters({
      level: 'primitive',
      domain: 'shared',
      fsdLayer: 'shared',
      owner: 'shared',
      dataProfile: 'static',
      designSource: 'dev-preview',
      states: ['closed', 'open', 'disabled-item'],
      usedBy: ['agent-studio'],
      interactionNotes: ['Actions log menu item selections through storybook/test fn spies.'],
      reuseNotes: ['Primitive menu used by Agent Studio cards and editor settings actions.'],
    }),
  },
} satisfies Meta<DropdownMenuStoryArgs>;

export default meta;

type Story = StoryObj<DropdownMenuStoryArgs>;

export const Playground: Story = {
  play: async ({ args, canvasElement, step, userEvent }) => {
    const canvas = within(canvasElement);
    const portal = within(document.body);

    await step('open dropdown menu', async () => {
      await userEvent.click(canvas.getByRole('button', { name: '에이전트 메뉴' }));
      await expect(await portal.findByRole('menuitem', { name: '복제하기' })).toBeInTheDocument();
    });

    await step('select duplicate action', async () => {
      await userEvent.click(portal.getByRole('menuitem', { name: '복제하기' }));
      await expect(args.onDuplicate).toHaveBeenCalled();
    });
  },
};

export const DisabledItem: Story = {
  args: {
    disabledArchive: true,
  },
};
