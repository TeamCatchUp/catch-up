'use client';

import { useState } from 'react';
import type { Meta, StoryObj } from '@storybook/nextjs-vite';
import { expect, fn, within } from 'storybook/test';

import { Button } from '@/shared/components/ui/button';

import { catchupParameters } from '../../../../../.storybook/catchupStoryParameters';
import RejectReasonDialog from './RejectReasonDialog';

interface RejectReasonDialogStoryArgs {
  initiallyOpen: boolean;
  submitting: boolean;
  onSubmit: (reason: string) => void;
}

function StatefulRejectReasonDialog(args: RejectReasonDialogStoryArgs) {
  const [open, setOpen] = useState(args.initiallyOpen);

  return (
    <div className="bg-fill-normal-normal flex min-h-40 items-center justify-center p-6">
      <Button variant="box-outline-gray" size="md" onClick={() => setOpen(true)}>
        사유 입력 열기
      </Button>
      <RejectReasonDialog open={open} onOpenChange={setOpen} submitting={args.submitting} onSubmit={args.onSubmit} />
    </div>
  );
}

const meta = {
  title: 'Compositions/LLM Wiki/ReviewQueue/RejectReasonDialog',
  tags: ['autodocs'],
  render: (args) => <StatefulRejectReasonDialog key={String(args.initiallyOpen)} {...args} />,
  args: { initiallyOpen: false, submitting: false, onSubmit: fn() },
  argTypes: {
    initiallyOpen: { control: 'boolean' },
    submitting: { control: 'boolean' },
    onSubmit: { control: false },
  },
  parameters: {
    ...catchupParameters({
      level: 'composition',
      domain: 'llm-wiki',
      fsdLayer: 'features',
      owner: 'feature',
      dataProfile: 'static',
      designSource: 'dev-preview',
      states: ['closed', 'open', 'empty-reason', 'submitting'],
      reuseNotes: ['Dialog·Button 프리미티브 조립 — ConfirmDialog의 여백·보더·버튼 배치를 따른다.'],
      dataNotes: ['사유가 비면 서버가 400으로 막아 제출 버튼을 먼저 잠근다.'],
    }),
  },
} satisfies Meta<RejectReasonDialogStoryArgs>;

export default meta;
type Story = StoryObj<RejectReasonDialogStoryArgs>;

/** 열자마자는 사유가 비어 제출이 잠겨 있고, 입력하면 풀린다. */
export const Playground: Story = {
  play: async ({ args, canvasElement, step, userEvent }) => {
    const canvas = within(canvasElement);
    const portal = within(document.body);

    await step('사유 입력 창을 연다', async () => {
      await userEvent.click(canvas.getByRole('button', { name: '사유 입력 열기' }));
      await expect(await portal.findByRole('dialog')).toBeInTheDocument();
    });

    const dialog = within(portal.getByRole('dialog'));

    await step('빈 사유는 제출할 수 없다', async () => {
      await expect(dialog.getByRole('button', { name: '전체 반려' })).toBeDisabled();
    });

    await step('사유를 넣으면 트림된 값으로 제출한다', async () => {
      await userEvent.type(dialog.getByRole('textbox', { name: '반려 사유' }), '  근거 문서가 없습니다  ');
      await expect(dialog.getByRole('button', { name: '전체 반려' })).toBeEnabled();
      await userEvent.click(dialog.getByRole('button', { name: '전체 반려' }));
      await expect(args.onSubmit).toHaveBeenCalledWith('근거 문서가 없습니다');
    });
  },
};

/** 제출 중 — 사유가 채워져 있어도 같은 요청이 두 번 나가지 않게 잠긴다. */
export const Submitting: Story = {
  args: { initiallyOpen: true, submitting: true },
  play: async ({ step, userEvent }) => {
    const portal = within(document.body);
    const dialog = within(await portal.findByRole('dialog'));

    await step('사유를 채워도 잠긴 채로 남는다', async () => {
      await userEvent.type(dialog.getByRole('textbox', { name: '반려 사유' }), '중복 제안');
      await expect(dialog.getByRole('button', { name: '전체 반려' })).toBeDisabled();
    });
  },
};
