import type { Meta, StoryObj } from '@storybook/nextjs-vite';
import { expect, within } from 'storybook/test';

import { catchupParameters } from '../../../../../../../.storybook/catchupStoryParameters';
import SlackGuideSection from './SlackGuideSection';

const meta = {
  title: 'Compositions/Admin/Integrations/Guides/SlackGuideSection',
  component: SlackGuideSection,
  tags: ['autodocs'],
  parameters: {
    ...catchupParameters({
      level: 'composition',
      domain: 'admin',
      fsdLayer: 'features',
      owner: 'feature',
      dataProfile: 'static',
      designSource: 'dev-preview',
      states: ['default'],
      dataNotes: [
        'PNG static import가 Storybook에서 렌더되는지 검증하는 스토리다.',
        'virtual:next-image가 Windows 경로 백슬래시를 먹으면 src에 "C:Users"가 들어간다.',
      ],
      reuseNotes: ['신규 디자인은 이 가이드를 커넥터 상세 본문의 아코디언 안에 넣는다.'],
    }),
  },
} satisfies Meta<typeof SlackGuideSection>;

export default meta;

type Story = StoryObj<typeof SlackGuideSection>;

export const Playground: Story = {
  render: () => (
    <div className="bg-fill-normal-normal flex w-200 flex-col p-6">
      <SlackGuideSection />
    </div>
  ),
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement);
    const images = canvas.getAllByRole('img') as HTMLImageElement[];

    await expect(images.length).toBe(2);

    for (const img of images) {
      const src = img.getAttribute('src') ?? '';

      // Windows 경로가 깨지면 백슬래시가 이스케이프로 먹혀 "C:Users..."가 된다
      await expect(src).not.toMatch(/C:Users/);
      // public/은 staticDirs로 루트에 서빙되므로 /public 접두사가 남으면 404다
      await expect(src).not.toMatch(/^\/public\//);

      // 경로가 그럴듯해도 실제로 로드되지 않으면 의미가 없다
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
