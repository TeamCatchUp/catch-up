'use client';

import type { Meta, StoryObj } from '@storybook/nextjs-vite';
import { expect, fn, within } from 'storybook/test';

import { catchupParameters } from '../../../../.storybook/catchupStoryParameters';
import { Button } from './button';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from './dialog';

interface DialogStoryArgs {
  title: string;
  description: string;
  hideClose: boolean;
  onSave: () => void;
}

const meta = {
  title: 'Primitives/Shared/Dialog',
  tags: ['autodocs'],
  args: {
    title: '에이전트 설정 저장',
    description: '변경한 실행 조건을 저장하기 전에 내용을 확인하세요.',
    hideClose: false,
    onSave: fn(),
  },
  argTypes: {
    title: {
      control: 'text',
    },
    description: {
      control: 'text',
    },
    hideClose: {
      control: 'boolean',
    },
    onSave: {
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
      states: ['closed', 'open', 'close-hidden'],
      usedBy: ['agent-studio'],
      interactionNotes: ['The play function opens the modal and verifies the title in the portal.'],
      reuseNotes: ['Primitive Radix dialog wrapper used by shared confirmation and feature modal surfaces.'],
    }),
  },
} satisfies Meta<DialogStoryArgs>;

export default meta;

type Story = StoryObj<DialogStoryArgs>;

export const Playground: Story = {
  render: ({ title, description, hideClose, onSave }) => (
    <div className="bg-fill-normal-normal flex min-h-40 items-center justify-center p-6">
      <Dialog>
        <DialogTrigger asChild>
          <Button variant="box-solid-primary" size="md">
            모달 열기
          </Button>
        </DialogTrigger>
        <DialogContent hideClose={hideClose}>
          <DialogHeader>
            <DialogTitle>{title}</DialogTitle>
            <DialogDescription>{description}</DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button variant="box-outline-gray" size="md">
              취소
            </Button>
            <Button variant="box-solid-primary" size="md" onClick={onSave}>
              저장
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  ),
  play: async ({ args, canvasElement, step, userEvent }) => {
    const canvas = within(canvasElement);
    const portal = within(document.body);

    await step('open dialog', async () => {
      await userEvent.click(canvas.getByRole('button', { name: '모달 열기' }));
      await expect(await portal.findByRole('dialog')).toBeInTheDocument();
      await expect(portal.getByRole('heading', { name: args.title })).toBeInTheDocument();
    });
  },
};

export const OpenState: Story = {
  render: ({ title, description, hideClose, onSave }) => (
    <div className="bg-fill-normal-normal flex min-h-40 items-center justify-center p-6">
      <Dialog defaultOpen>
        <DialogTrigger asChild>
          <Button variant="box-solid-primary" size="md">
            모달 열기
          </Button>
        </DialogTrigger>
        <DialogContent hideClose={hideClose}>
          <DialogHeader>
            <DialogTitle>{title}</DialogTitle>
            <DialogDescription>{description}</DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button variant="box-outline-gray" size="md">
              취소
            </Button>
            <Button variant="box-solid-primary" size="md" onClick={onSave}>
              저장
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  ),
};
