import type { Meta, StoryObj } from '@storybook/nextjs-vite';
import { expect, within } from 'storybook/test';

import { catchupParameters } from '../../../../../../../.storybook/catchupStoryParameters';
import ConnectorGuideAccordion from './ConnectorGuideAccordion';
import SlackGuideSection from './SlackGuideSection';

const meta = {
  title: 'Compositions/Admin/Integrations/Guides/ConnectorGuideAccordion',
  component: ConnectorGuideAccordion,
  tags: ['autodocs'],
  args: { service: 'slack', children: <SlackGuideSection /> },
  parameters: {
    ...catchupParameters({
      level: 'composition',
      domain: 'admin',
      fsdLayer: 'features',
      owner: 'feature',
      dataProfile: 'static',
      designSource: 'figma',
      figma: {
        url: 'https://www.figma.com/design/7UwupbVvmHkElmP2OBJQio/Design-System?node-id=16966-26874',
        fileKey: '7UwupbVvmHkElmP2OBJQio',
        nodeId: '16966:26874',
      },
      viewport: { width: 780, height: 400 },
      states: ['collapsed', 'expanded'],
      reuseNotes: ['기존 *GuideSection 4종을 children으로 감싼다 — 내용은 손대지 않는다.'],
      dataNotes: ['펼침 상태는 계획 ①의 next/image 대체가 동작해야 검증된다. PNG static import가 들어 있다.'],
    }),
  },
} satisfies Meta<typeof ConnectorGuideAccordion>;

export default meta;

type Story = StoryObj<typeof ConnectorGuideAccordion>;

const Frame = ({ children }: { children: React.ReactNode }) => (
  <div className="bg-fill-normal-normal w-195 p-6">{children}</div>
);

export const Collapsed: Story = {
  render: (args) => (
    <Frame>
      <ConnectorGuideAccordion {...args} />
    </Frame>
  ),
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement);
    const trigger = canvas.getByRole('button', { name: /Slack 연동 가이드 보기/ });

    await expect(trigger).toHaveAttribute('aria-expanded', 'false');
    await expect(canvas.queryByText('1. 워크스페이스 연결')).not.toBeInTheDocument();
  },
};

export const Expanded: Story = {
  render: (args) => (
    <Frame>
      <ConnectorGuideAccordion {...args} />
    </Frame>
  ),
  play: async ({ canvasElement, userEvent }) => {
    const canvas = within(canvasElement);

    await userEvent.click(canvas.getByRole('button', { name: /Slack 연동 가이드 보기/ }));
    await expect(canvas.getByText('1. 워크스페이스 연결')).toBeInTheDocument();

    // 가이드의 PNG가 실제로 로드되는지 — 경로만 그럴듯하고 404이면 안 된다
    const images = canvas.getAllByRole('img') as HTMLImageElement[];
    await expect(images.length).toBe(2);

    for (const img of images) {
      await expect(img.getAttribute('src') ?? '').not.toMatch(/C:Users|^\/public\//);
      if (!img.complete) {
        await new Promise((resolve) => {
          img.addEventListener('load', resolve, { once: true });
          img.addEventListener('error', resolve, { once: true });
        });
      }
      await expect(img.naturalWidth).toBeGreaterThan(0);
    }
  },
};
