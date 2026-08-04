import type { Meta, StoryObj } from '@storybook/nextjs-vite';
import { expect, fn, within } from 'storybook/test';

import { catchupParameters } from '../../../../../../../.storybook/catchupStoryParameters';
import MappingCheckPopover from './MappingCheckPopover';

const meta = {
  title: 'Compositions/Admin/Integrations/Detail/MappingCheckPopover',
  component: MappingCheckPopover,
  tags: ['autodocs'],
  args: { onClose: fn() },
  parameters: {
    ...catchupParameters({
      level: 'composition',
      domain: 'admin',
      fsdLayer: 'features',
      owner: 'feature',
      dataProfile: 'static',
      designSource: 'figma',
      figma: {
        url: 'https://www.figma.com/design/7UwupbVvmHkElmP2OBJQio/Design-System?node-id=17251-77202',
        fileKey: '7UwupbVvmHkElmP2OBJQio',
        nodeId: '17251:77202',
      },
      viewport: { width: 480, height: 200 },
      states: ['default'],
      dataNotes: [
        '본문은 온보딩 문서("처음 오셨나요? — 나의 이름표") 기반으로 교체 (사용자 지시 2026-08-04). Figma 원문("권한에 맞는 검색 결과")은 스펙 미결 #1이었다.',
        'Figma 17251:77261 매핑 확인 모달은 구현하지 않는다 (스펙 결정 #1). 이 팝오버가 비차단 안내를 맡는다.',
      ],
    }),
  },
} satisfies Meta<typeof MappingCheckPopover>;

export default meta;

type Story = StoryObj<typeof MappingCheckPopover>;

export const Default: Story = {
  render: (args) => (
    <div className="bg-fill-normal-normal p-6">
      <MappingCheckPopover {...args} />
    </div>
  ),
  play: async ({ canvasElement, userEvent, args }) => {
    const canvas = within(canvasElement);

    await expect(canvas.getByText('연동 전, 이용자 매핑 상태를 확인해 주세요')).toBeInTheDocument();
    await expect(canvas.getByText(/나의 업무 맥락/)).toBeInTheDocument();

    await userEvent.click(canvas.getByRole('button', { name: '닫기' }));
    await expect(args.onClose).toHaveBeenCalled();
  },
};
