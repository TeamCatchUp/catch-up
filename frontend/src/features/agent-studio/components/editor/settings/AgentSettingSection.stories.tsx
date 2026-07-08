import type { Meta, StoryObj } from '@storybook/nextjs-vite';
import { expect, fn, within } from 'storybook/test';

import TagIcon from '@/public/icons/icon/tag.svg';

import { catchupParameters } from '../../../../../../.storybook/catchupStoryParameters';
import { AGENT_STUDIO_SETTINGS_FIXTURE } from '../../../fixtures/agentStudioFixtures';
import AgentSettingSection from './AgentSettingSection';
import AgentInstructionField from './fields/AgentInstructionField';
import AgentSelectField from './fields/AgentSelectField';

interface AgentSettingSectionStoryArgs {
  step: 1 | 2;
  title: string;
  description: string;
  disabled: boolean;
  onSelectChange: (value: string) => void;
  onInstructionChange: (value: string) => void;
}

const meta = {
  title: 'Compositions/Agent Studio/Editor/AgentSettingSection',
  component: AgentSettingSection,
  tags: ['autodocs'],
  args: {
    step: 2,
    title: 'Slack으로 메시지 보내기',
    description: '완성된 문의 대응 가이드라인을 전송할 메시지를 찾습니다.',
    disabled: false,
    onSelectChange: fn(),
    onInstructionChange: fn(),
  },
  argTypes: {
    step: {
      control: 'inline-radio',
      options: [1, 2],
    },
    disabled: {
      control: 'boolean',
    },
    onSelectChange: {
      control: false,
    },
    onInstructionChange: {
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
      states: ['step-one', 'step-two', 'disabled-fields'],
      reuseNotes: ['Section composes editor field controls while owning step title and bordered body layout.'],
    }),
  },
} satisfies Meta<AgentSettingSectionStoryArgs>;

export default meta;

type Story = StoryObj<AgentSettingSectionStoryArgs>;

export const Playground: Story = {
  render: ({ step, title, description, disabled, onSelectChange, onInstructionChange }) => (
    <div className="bg-fill-normal-assistive-dark flex min-h-160 items-start p-8">
      <div className="w-full max-w-180">
        <AgentSettingSection step={step} title={title} description={description}>
          <AgentSelectField
            required
            label="채널톡을 연동한 Slack 채널을 선택해주세요."
            value="C_HELPDESK"
            icon={<TagIcon className="size-5.5" aria-hidden="true" />}
            items={[
              { value: 'C_HELPDESK', label: '#support-agent' },
              { value: 'C_ISSUE', label: '#issue-triage' },
            ]}
            disabled={disabled}
            onChange={onSelectChange}
          />
          <AgentInstructionField
            value="고객이 이미 시도한 해결 방법을 먼저 요약하고, 다음 액션을 짧게 제안해주세요."
            hintText={AGENT_STUDIO_SETTINGS_FIXTURE.instructionHintText}
            disabled={disabled}
            onChange={onInstructionChange}
          />
        </AgentSettingSection>
      </div>
    </div>
  ),
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement);

    await expect(canvas.getByRole('heading', { name: 'Slack으로 메시지 보내기' })).toBeInTheDocument();
    await expect(canvas.getByRole('combobox', { name: /Slack 채널/ })).toBeInTheDocument();
  },
};
