'use client';

import { useState } from 'react';
import type { Meta, StoryObj } from '@storybook/nextjs-vite';
import { expect, fn, within } from 'storybook/test';

import { catchupParameters } from '../../../../../../../.storybook/catchupStoryParameters';
import { AGENT_STUDIO_SETTINGS_FIXTURE } from '../../../../fixtures/agentStudioFixtures';
import AgentInstructionField from './AgentInstructionField';

type InstructionPreset = 'empty' | 'short-rule' | 'long-rule';

interface AgentInstructionFieldStoryArgs {
  preset: InstructionPreset;
  disabled: boolean;
  onChange: (value: string) => void;
}

const instructionPresetOptions: readonly InstructionPreset[] = ['empty', 'short-rule', 'long-rule'];

const instructionText = {
  empty: '',
  'short-rule': '고객의 질문을 먼저 요약하고, 다음 액션을 한 문장으로 제안해주세요.',
  'long-rule':
    '고객이 이미 시도한 해결 방법을 먼저 정리하고, 관련 문서 링크가 있을 때만 함께 첨부해주세요.\n운영팀이 바로 복사해도 어색하지 않도록 짧은 문장과 명확한 체크리스트를 사용해주세요.',
} satisfies Record<InstructionPreset, string>;

function StatefulAgentInstructionField(args: AgentInstructionFieldStoryArgs) {
  const [value, setValue] = useState(instructionText[args.preset]);

  return (
    <div className="bg-fill-normal-assistive-dark flex min-h-80 items-start p-8">
      <div className="w-full max-w-160">
        <AgentInstructionField
          value={value}
          hintText={AGENT_STUDIO_SETTINGS_FIXTURE.instructionHintText}
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
  title: 'Compositions/Agent Studio/Editor/AgentInstructionField',
  tags: ['autodocs'],
  args: {
    preset: 'short-rule',
    disabled: false,
    onChange: fn(),
  },
  argTypes: {
    preset: {
      control: 'inline-radio',
      options: instructionPresetOptions,
    },
    disabled: {
      control: 'boolean',
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
      states: ['empty', 'filled', 'multiline', 'disabled', 'focused'],
      reuseNotes: ['Feature-specific textarea field for Agent guide instructions.'],
      interactionNotes: ['The play function types into the textarea and verifies callback wiring.'],
    }),
  },
} satisfies Meta<AgentInstructionFieldStoryArgs>;

export default meta;

type Story = StoryObj<AgentInstructionFieldStoryArgs>;

export const Playground: Story = {
  render: (args) => <StatefulAgentInstructionField key={`${args.preset}:${args.disabled}`} {...args} />,
  play: async ({ args, canvasElement, userEvent }) => {
    if (args.disabled) return;

    const canvas = within(canvasElement);
    const textarea = canvas.getByRole('textbox', { name: '답변 초안, 어떤 규칙으로 쓸까요?' });

    await userEvent.click(textarea);
    await userEvent.type(textarea, ' 응답 톤은 친절하게 유지합니다.');
    await expect(args.onChange).toHaveBeenCalled();
  },
};

export const Disabled: Story = {
  args: {
    preset: 'long-rule',
    disabled: true,
  },
};
