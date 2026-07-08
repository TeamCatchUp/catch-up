import type { Meta, StoryObj } from '@storybook/nextjs-vite';
import { expect, fn, within } from 'storybook/test';

import { catchupParameters } from '../../../../../../.storybook/catchupStoryParameters';
import AgentCreateButton from './AgentCreateButton';

const meta = {
  title: 'Compositions/Agent Studio/List/AgentCreateButton',
  component: AgentCreateButton,
  tags: ['autodocs'],
  args: {
    disabled: false,
    onClick: fn(),
  },
  argTypes: {
    disabled: {
      control: 'boolean',
    },
    onClick: {
      control: false,
    },
  },
  parameters: {
    ...catchupParameters({
      level: 'composition',
      domain: 'agent-studio',
      fsdLayer: 'features',
      owner: 'feature',
      dataProfile: 'static',
      designSource: 'figma',
      states: ['default', 'disabled'],
      reuseNotes: ['Feature-specific create CTA for the Agent Studio list toolbar.'],
      interactionNotes: ['The play function verifies click wiring through the Actions panel callback.'],
    }),
  },
} satisfies Meta<typeof AgentCreateButton>;

export default meta;

type Story = StoryObj<typeof meta>;

export const Playground: Story = {
  render: (args) => (
    <div className="bg-fill-normal-normal flex min-h-32 items-start p-6">
      <AgentCreateButton {...args} />
    </div>
  ),
  play: async ({ args, canvasElement, userEvent }) => {
    const canvas = within(canvasElement);

    await userEvent.click(canvas.getByRole('button', { name: 'Agent 만들기' }));
    await expect(args.onClick).toHaveBeenCalled();
  },
};

export const Disabled: Story = {
  args: {
    disabled: true,
  },
  parameters: {
    ...catchupParameters({
      level: 'composition',
      domain: 'agent-studio',
      fsdLayer: 'features',
      owner: 'feature',
      dataProfile: 'static',
      designSource: 'figma',
      states: ['disabled'],
    }),
  },
  render: (args) => (
    <div className="bg-fill-normal-normal flex min-h-32 items-start p-6">
      <AgentCreateButton {...args} />
    </div>
  ),
};
