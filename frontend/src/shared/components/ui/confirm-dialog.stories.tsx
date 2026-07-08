'use client';

import { useState } from 'react';
import type { Meta, StoryObj } from '@storybook/nextjs-vite';
import { expect, fn, within } from 'storybook/test';

import { catchupParameters } from '../../../../.storybook/catchupStoryParameters';
import { Button } from './button';
import type { ConfirmDialogProps } from './confirm-dialog';
import { ConfirmDialog } from './confirm-dialog';

const confirmDialogVariants = ['primary', 'danger', 'blue', 'mono'] as const satisfies readonly NonNullable<
  ConfirmDialogProps['variant']
>[];

interface ConfirmDialogStoryArgs {
  title: string;
  description: string;
  confirmLabel: string;
  cancelLabel: string;
  variant: (typeof confirmDialogVariants)[number];
  hideCancel: boolean;
  initiallyOpen: boolean;
  onConfirm: () => void;
}

function StatefulConfirmDialog(args: ConfirmDialogStoryArgs) {
  const [open, setOpen] = useState(args.initiallyOpen);

  return (
    <div className="bg-fill-normal-normal flex min-h-40 items-center justify-center p-6">
      <Button variant="box-solid-primary" size="md" onClick={() => setOpen(true)}>
        확인창 열기
      </Button>
      <ConfirmDialog
        open={open}
        onOpenChange={setOpen}
        title={args.title}
        description={args.description}
        confirmLabel={args.confirmLabel}
        cancelLabel={args.cancelLabel}
        variant={args.variant}
        hideCancel={args.hideCancel}
        onConfirm={args.onConfirm}
      />
    </div>
  );
}

const meta = {
  title: 'Compositions/Shared/Feedback/ConfirmDialog',
  tags: ['autodocs'],
  args: {
    title: '에이전트를 삭제할까요?',
    description: '삭제한 에이전트는 다시 복구할 수 없습니다.',
    confirmLabel: '삭제',
    cancelLabel: '취소',
    variant: 'danger',
    hideCancel: false,
    initiallyOpen: false,
    onConfirm: fn(),
  },
  argTypes: {
    title: {
      control: 'text',
    },
    description: {
      control: 'text',
    },
    confirmLabel: {
      control: 'text',
    },
    cancelLabel: {
      control: 'text',
    },
    variant: {
      control: 'inline-radio',
      options: confirmDialogVariants,
    },
    hideCancel: {
      control: 'boolean',
    },
    initiallyOpen: {
      control: 'boolean',
    },
    onConfirm: {
      control: false,
    },
  },
  parameters: {
    ...catchupParameters({
      level: 'composition',
      domain: 'shared',
      fsdLayer: 'shared',
      owner: 'shared',
      dataProfile: 'static',
      designSource: 'dev-preview',
      states: ['closed', 'open', 'danger', 'primary', 'blue', 'mono', 'alert-only'],
      usedBy: ['agent-studio'],
      interactionNotes: ['The play function opens the dialog, confirms, and checks the callback.'],
      reuseNotes: ['Shared feedback composition built from Dialog and Button primitives.'],
    }),
  },
} satisfies Meta<ConfirmDialogStoryArgs>;

export default meta;

type Story = StoryObj<ConfirmDialogStoryArgs>;

export const Playground: Story = {
  render: (args) => <StatefulConfirmDialog key={`${args.variant}:${args.initiallyOpen}`} {...args} />,
  play: async ({ args, canvasElement, step, userEvent }) => {
    const canvas = within(canvasElement);
    const portal = within(document.body);

    await step('open confirm dialog', async () => {
      await userEvent.click(canvas.getByRole('button', { name: '확인창 열기' }));
      await expect(await portal.findByRole('dialog')).toBeInTheDocument();
      await expect(portal.getByRole('heading', { name: args.title })).toBeInTheDocument();
    });

    await step('confirm action', async () => {
      await userEvent.click(portal.getByRole('button', { name: args.confirmLabel }));
      await expect(args.onConfirm).toHaveBeenCalled();
    });
  },
};

export const VariantSet: Story = {
  args: {
    onConfirm: fn(),
  },
  render: ({ title, description, cancelLabel, hideCancel, onConfirm }) => (
    <div className="bg-fill-normal-normal grid min-h-56 gap-3 p-6">
      {confirmDialogVariants.map((variant) => (
        <StatefulConfirmDialog
          key={variant}
          title={title}
          description={description}
          confirmLabel={variant}
          cancelLabel={cancelLabel}
          variant={variant}
          hideCancel={hideCancel}
          initiallyOpen={variant === 'primary'}
          onConfirm={onConfirm}
        />
      ))}
      <StatefulConfirmDialog
        title="변경 사항을 저장했습니다"
        description="새 설정은 다음 문의부터 적용됩니다."
        confirmLabel="확인"
        cancelLabel={cancelLabel}
        variant="primary"
        hideCancel
        initiallyOpen={false}
        onConfirm={onConfirm}
      />
    </div>
  ),
};
