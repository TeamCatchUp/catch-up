'use client';

import type { Meta, StoryObj } from '@storybook/nextjs-vite';
import { expect, fn, within } from 'storybook/test';

import { catchupParameters } from '../../../../.storybook/catchupStoryParameters';
import { Input } from './input';

interface InputStoryArgs {
  inputSize: 'lg' | 'sm';
  placeholder: string;
  value: string;
  disabled: boolean;
  error: boolean;
  onChange: () => void;
}

const inputSizes = ['lg', 'sm'] as const;

const meta = {
  title: 'Primitives/Shared/Input',
  tags: ['autodocs'],
  args: {
    inputSize: 'lg',
    placeholder: '워크스페이스 이름을 입력하세요',
    value: '',
    disabled: false,
    error: false,
    onChange: fn(),
  },
  argTypes: {
    inputSize: {
      control: 'inline-radio',
      options: inputSizes,
    },
    placeholder: {
      control: 'text',
    },
    value: {
      control: 'text',
    },
    disabled: {
      control: 'boolean',
    },
    error: {
      control: 'boolean',
    },
    onChange: {
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
      states: ['default', 'filled', 'disabled', 'error', 'sizes'],
      usedBy: ['agent-studio'],
      interactionNotes: ['The play function types into the input and logs change events.'],
      reuseNotes: ['Primitive input used by forms, filters, and search compositions.'],
    }),
  },
} satisfies Meta<InputStoryArgs>;

export default meta;

type Story = StoryObj<InputStoryArgs>;

export const Playground: Story = {
  render: ({ value, inputSize, placeholder, disabled, error, onChange }) => (
    <div className="bg-fill-normal-normal flex min-h-32 items-start p-6">
      <div className="w-96">
        <Input
          aria-label="텍스트 입력"
          value={value}
          inputSize={inputSize}
          placeholder={placeholder}
          disabled={disabled}
          error={error}
          onChange={onChange}
        />
      </div>
    </div>
  ),
  play: async ({ args, canvasElement, userEvent }) => {
    if (args.disabled) return;

    const canvas = within(canvasElement);
    const input = canvas.getByRole('textbox', { name: '텍스트 입력' });
    await userEvent.type(input, 'CatchUp');
    await expect(args.onChange).toHaveBeenCalled();
  },
};

export const StateSet: Story = {
  args: {
    onChange: fn(),
  },
  render: ({ placeholder, onChange }) => (
    <div className="bg-fill-normal-normal grid max-w-120 gap-3 p-6">
      <Input aria-label="기본 입력" inputSize="lg" placeholder={placeholder} onChange={onChange} />
      <Input aria-label="값 입력" inputSize="lg" value="CatchUp 고객 문의" onChange={onChange} />
      <Input aria-label="오류 입력" inputSize="lg" value="필수 값 누락" error onChange={onChange} />
      <Input aria-label="비활성 입력" inputSize="lg" value="수정할 수 없음" disabled onChange={onChange} />
      <Input aria-label="작은 입력" inputSize="sm" placeholder="필터 입력" onChange={onChange} />
    </div>
  ),
};
