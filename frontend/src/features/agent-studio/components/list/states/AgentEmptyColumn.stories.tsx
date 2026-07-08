import type { Meta, StoryObj } from '@storybook/nextjs-vite';

import { catchupParameters } from '../../../../../../.storybook/catchupStoryParameters';
import type { AgentStatusSectionLabel } from '../content/AgentStatusSection';
import AgentEmptyColumn from './AgentEmptyColumn';

interface AgentEmptyColumnStoryArgs {
  label: AgentStatusSectionLabel;
  title: string;
  description: string;
  count: number;
}

const labelOptions: readonly AgentStatusSectionLabel[] = ['운영중', '제작중', '사용 안함'];

const emptyTextByLabel = {
  운영중: {
    title: '운영 중인 Agent가 없습니다.',
    description: '새로운 Agent를 만들어\n반복되는 문의 업무를 자동화해보세요.',
  },
  제작중: {
    title: '제작 중인 Agent가 없습니다.',
    description: '새로운 Agent를 만들어\n반복되는 문의 업무를 자동화해보세요.',
  },
  '사용 안함': {
    title: '아직 비활성 Agent가 없습니다.',
    description: '사용을 중지한 Agent는 이곳에 보관됩니다.',
  },
} satisfies Record<AgentStatusSectionLabel, Pick<AgentEmptyColumnStoryArgs, 'title' | 'description'>>;

const meta = {
  title: 'Compositions/Agent Studio/List/AgentEmptyColumn',
  component: AgentEmptyColumn,
  tags: ['autodocs'],
  args: {
    label: '운영중',
    title: emptyTextByLabel.운영중.title,
    description: emptyTextByLabel.운영중.description,
    count: 0,
  },
  argTypes: {
    label: {
      control: 'inline-radio',
      options: labelOptions,
    },
    count: {
      control: { type: 'number', min: 0, max: 9, step: 1 },
    },
  },
  parameters: {
    ...catchupParameters({
      level: 'composition',
      domain: 'agent-studio',
      fsdLayer: 'features',
      owner: 'feature',
      dataProfile: 'empty',
      designSource: 'figma',
      states: ['active-empty', 'draft-empty', 'inactive-empty'],
      dataNotes: ['Empty copy differs by status column.'],
    }),
  },
} satisfies Meta<AgentEmptyColumnStoryArgs>;

export default meta;

type Story = StoryObj<AgentEmptyColumnStoryArgs>;

export const Playground: Story = {
  render: ({ label, count }) => {
    const copy = emptyTextByLabel[label];

    return (
      <div className="bg-fill-normal-normal flex min-h-96 items-start p-6">
        <AgentEmptyColumn label={label} count={count} title={copy.title} description={copy.description} />
      </div>
    );
  },
};

export const StateSet: Story = {
  parameters: {
    ...catchupParameters({
      level: 'composition',
      domain: 'agent-studio',
      fsdLayer: 'features',
      owner: 'feature',
      dataProfile: 'empty',
      designSource: 'figma',
      states: ['active-empty', 'draft-empty', 'inactive-empty'],
    }),
  },
  render: () => (
    <div className="bg-fill-normal-normal flex min-h-96 flex-wrap items-start gap-6 p-6">
      {labelOptions.map((label) => {
        const copy = emptyTextByLabel[label];

        return <AgentEmptyColumn key={label} label={label} title={copy.title} description={copy.description} />;
      })}
    </div>
  ),
};
