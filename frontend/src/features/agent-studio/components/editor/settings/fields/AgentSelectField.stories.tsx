'use client';

import { useState } from 'react';
import type { Meta, StoryObj } from '@storybook/nextjs-vite';
import { expect, fn, within } from 'storybook/test';

import ClockIcon from '@/public/icons/icon/clock.svg';
import TagIcon from '@/public/icons/icon/tag.svg';

import { catchupParameters } from '../../../../../../../.storybook/catchupStoryParameters';
import type { AgentStudioSelectItem } from '../../../../types/agentStudioModel';
import AgentSelectField from './AgentSelectField';

interface AgentSelectFieldStoryArgs {
  value: string;
  placeholder: string;
  required: boolean;
  disabled: boolean;
  withIcon: boolean;
  optionSet: 'channels' | 'quiet-periods';
  onChange: (value: string) => void;
}

const optionSetOptions: readonly AgentSelectFieldStoryArgs['optionSet'][] = ['channels', 'quiet-periods'];

const selectItems = {
  channels: [
    { value: 'channel-talk-support', label: 'CatchUp 고객 문의' },
    { value: 'channel-talk-vip', label: 'VIP 문의 채널' },
    { value: 'channel-talk-archive', label: '보관 채널', disabled: true },
  ],
  'quiet-periods': [
    { value: '60', label: '1분' },
    { value: '180', label: '3분' },
    { value: '300', label: '5분' },
    { value: '600', label: '10분' },
  ],
} satisfies Record<AgentSelectFieldStoryArgs['optionSet'], readonly AgentStudioSelectItem[]>;

function StatefulAgentSelectField(args: AgentSelectFieldStoryArgs) {
  const [value, setValue] = useState(args.value);
  const isQuietPeriod = args.optionSet === 'quiet-periods';

  return (
    <div className="bg-fill-normal-assistive-dark flex min-h-80 items-start p-8">
      <div className="w-full max-w-160">
        <AgentSelectField
          required={args.required}
          label={isQuietPeriod ? '고객의 마지막 문의 메시지가 들어온 후 몇 분 후에 Agent를 실행할까요?' : '어떤 채널로 들어오는 문의를 감지할까요?'}
          value={value}
          placeholder={args.placeholder}
          icon={
            args.withIcon ? (
              isQuietPeriod ? (
                <ClockIcon className="size-5.5" aria-hidden="true" />
              ) : (
                <TagIcon className="size-5.5" aria-hidden="true" />
              )
            ) : undefined
          }
          items={selectItems[args.optionSet]}
          disabled={args.disabled}
          onChange={(next) => {
            setValue(next);
            args.onChange(next);
          }}
        />
      </div>
    </div>
  );
}

const meta = {
  title: 'Compositions/Agent Studio/Editor/AgentSelectField',
  tags: ['autodocs'],
  args: {
    value: '',
    placeholder: '채널을 선택해주세요',
    required: true,
    disabled: false,
    withIcon: true,
    optionSet: 'channels',
    onChange: fn(),
  },
  argTypes: {
    value: {
      control: 'text',
    },
    required: {
      control: 'boolean',
    },
    disabled: {
      control: 'boolean',
    },
    withIcon: {
      control: 'boolean',
    },
    optionSet: {
      control: 'inline-radio',
      options: optionSetOptions,
    },
    onChange: {
      control: false,
    },
  },
  parameters: {
    ...catchupParameters({
      level: 'composition',
      domain: 'agent-studio',
      fsdLayer: 'features',
      owner: 'feature',
      dataProfile: 'realistic-fixture',
      designSource: 'figma',
      states: ['placeholder', 'selected', 'disabled', 'required'],
      reuseNotes: ['Feature-specific field wrapper around shared Select primitives.'],
      interactionNotes: ['The play function opens the select and chooses a channel option.'],
    }),
  },
} satisfies Meta<AgentSelectFieldStoryArgs>;

export default meta;

type Story = StoryObj<AgentSelectFieldStoryArgs>;

export const Playground: Story = {
  render: (args) => <StatefulAgentSelectField key={`${args.optionSet}:${args.value}:${args.disabled}`} {...args} />,
  play: async ({ args, canvasElement, step, userEvent }) => {
    if (args.disabled) return;

    const canvas = within(canvasElement);
    const portal = within(document.body);

    await step('open select menu', async () => {
      await userEvent.click(canvas.getByRole('combobox'));
      await expect(await portal.findByRole('option', { name: 'CatchUp 고객 문의' })).toBeInTheDocument();
    });

    await step('choose channel option', async () => {
      await userEvent.click(portal.getByRole('option', { name: 'CatchUp 고객 문의' }));
      await expect(args.onChange).toHaveBeenCalledWith('channel-talk-support');
    });
  },
};

export const Disabled: Story = {
  args: {
    disabled: true,
    value: 'channel-talk-support',
  },
};
