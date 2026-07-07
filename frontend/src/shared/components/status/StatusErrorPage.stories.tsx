'use client';

import type { Meta, StoryObj } from '@storybook/nextjs-vite';
import { expect, within } from 'storybook/test';

import { catchupParameters } from '../../../../.storybook/catchupStoryParameters';
import StatusErrorPage from './StatusErrorPage';
import { STATUS_IMAGES } from './statusImages';

type StatusErrorKind = 'not-found' | 'forbidden';
type ThemeMode = 'light' | 'dark';

interface StatusErrorPageStoryArgs {
  status: StatusErrorKind;
  theme: ThemeMode;
}

const statusOptions: readonly StatusErrorKind[] = ['not-found', 'forbidden'];
const themeOptions: readonly ThemeMode[] = ['light', 'dark'];

const statusFixtures: Record<
  StatusErrorKind,
  {
    title: string;
    description: string;
    image: (typeof STATUS_IMAGES)[keyof typeof STATUS_IMAGES];
    primaryAction: { label: string; href: string };
    secondaryAction?: { label: string; action: 'back' };
  }
> = {
  'not-found': {
    title: '찾으시는 페이지가 없어요',
    description: '주소가 잘못되었거나, 페이지가 이동했을 수 있어요',
    image: STATUS_IMAGES.notFound,
    secondaryAction: { label: '이전 페이지', action: 'back' } as const,
    primaryAction: { label: '홈으로 돌아가기', href: '/' },
  },
  forbidden: {
    title: '이 대화는 질문자 본인만 볼 수 있어요',
    description: '다른 구성원의 대화 내용은 공개되지 않아요',
    image: STATUS_IMAGES.forbidden,
    primaryAction: { label: 'Catch Up에서 직접 검색하기', href: '/' },
  },
};

function StatusCanvas({ status, theme }: StatusErrorPageStoryArgs) {
  const fixture = statusFixtures[status];

  return (
    <div
      className={`${theme === 'dark' ? 'dark ' : ''}bg-background-normal-normal`}
      style={{ minHeight: 625 }}
    >
      <StatusErrorPage
        title={fixture.title}
        description={fixture.description}
        image={fixture.image}
        secondaryAction={fixture.secondaryAction}
        primaryAction={fixture.primaryAction}
      />
    </div>
  );
}

const meta = {
  title: 'Screens/Shared/Status/StatusErrorPage',
  tags: ['autodocs'],
  args: {
    status: 'not-found',
    theme: 'light',
  },
  argTypes: {
    status: {
      control: 'inline-radio',
      options: statusOptions,
    },
    theme: {
      control: 'inline-radio',
      options: themeOptions,
    },
  },
  parameters: {
    ...catchupParameters({
      level: 'screen',
      domain: 'shared',
      fsdLayer: 'shared',
      owner: 'shared',
      dataProfile: 'static',
      designSource: 'figma',
      states: ['not-found-light', 'not-found-dark', 'forbidden-light', 'forbidden-dark'],
      reuseNotes: [
        'Status actions reuse shared Button variants.',
        'Status illustrations reuse STATUS_IMAGES light/dark image pairs.',
      ],
      tokenNotes: [
        'Figma gap/36 maps to gap-9.',
        'Figma gap/16 maps to gap-4 in the not-found action row.',
      ],
    }),
  },
} satisfies Meta<StatusErrorPageStoryArgs>;

export default meta;

type Story = StoryObj<StatusErrorPageStoryArgs>;

export const Playground: Story = {
  render: (args) => <StatusCanvas {...args} />,
};

export const NotFoundLight: Story = {
  args: {
    status: 'not-found',
    theme: 'light',
  },
  parameters: {
    ...catchupParameters({
      level: 'screen',
      domain: 'shared',
      fsdLayer: 'shared',
      owner: 'shared',
      dataProfile: 'static',
      figmaLab: {
        caseId: 'status-not-found-light',
        groupId: 'shared-status',
      },
      designSource: 'figma',
      figma: {
        url: 'https://www.figma.com/design/7UwupbVvmHkElmP2OBJQio/%F0%9F%8D%85-Design-System?node-id=10328-183838&m=dev',
        fileKey: '7UwupbVvmHkElmP2OBJQio',
        nodeId: '10328:183838',
      },
      viewport: {
        width: 1024,
        height: 625,
      },
      states: ['light'],
    }),
  },
  render: (args) => <StatusCanvas {...args} />,
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement);
    await expect(canvas.getByRole('heading', { name: '찾으시는 페이지가 없어요' })).toBeInTheDocument();
    await expect(canvas.getByRole('link', { name: '홈으로 돌아가기' })).toBeInTheDocument();
  },
};

export const NotFoundDark: Story = {
  args: {
    status: 'not-found',
    theme: 'dark',
  },
  parameters: {
    ...catchupParameters({
      level: 'screen',
      domain: 'shared',
      fsdLayer: 'shared',
      owner: 'shared',
      dataProfile: 'static',
      figmaLab: {
        caseId: 'status-not-found-dark',
        groupId: 'shared-status',
      },
      designSource: 'figma',
      figma: {
        url: 'https://www.figma.com/design/7UwupbVvmHkElmP2OBJQio/%F0%9F%8D%85-Design-System?node-id=10328-184247&m=dev',
        fileKey: '7UwupbVvmHkElmP2OBJQio',
        nodeId: '10328:184247',
      },
      viewport: {
        width: 1024,
        height: 625,
      },
      states: ['dark'],
    }),
  },
  render: (args) => <StatusCanvas {...args} />,
};

export const ForbiddenLight: Story = {
  args: {
    status: 'forbidden',
    theme: 'light',
  },
  parameters: {
    ...catchupParameters({
      level: 'screen',
      domain: 'shared',
      fsdLayer: 'shared',
      owner: 'shared',
      dataProfile: 'static',
      figmaLab: {
        caseId: 'status-forbidden-light',
        groupId: 'shared-status',
      },
      designSource: 'figma',
      figma: {
        url: 'https://www.figma.com/design/7UwupbVvmHkElmP2OBJQio/%F0%9F%8D%85-Design-System?node-id=10328-183816&m=dev',
        fileKey: '7UwupbVvmHkElmP2OBJQio',
        nodeId: '10328:183816',
      },
      viewport: {
        width: 1024,
        height: 625,
      },
      states: ['light'],
    }),
  },
  render: (args) => <StatusCanvas {...args} />,
};

export const ForbiddenDark: Story = {
  args: {
    status: 'forbidden',
    theme: 'dark',
  },
  parameters: {
    ...catchupParameters({
      level: 'screen',
      domain: 'shared',
      fsdLayer: 'shared',
      owner: 'shared',
      dataProfile: 'static',
      figmaLab: {
        caseId: 'status-forbidden-dark',
        groupId: 'shared-status',
      },
      designSource: 'figma',
      figma: {
        url: 'https://www.figma.com/design/7UwupbVvmHkElmP2OBJQio/%F0%9F%8D%85-Design-System?node-id=10328-184227&m=dev',
        fileKey: '7UwupbVvmHkElmP2OBJQio',
        nodeId: '10328:184227',
      },
      viewport: {
        width: 1024,
        height: 625,
      },
      states: ['dark'],
    }),
  },
  render: (args) => <StatusCanvas {...args} />,
};
