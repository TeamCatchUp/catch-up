import type { Meta, StoryObj } from '@storybook/nextjs-vite';
import { expect, fn, userEvent, within } from 'storybook/test';

import IconArrowDown from '@/public/icons/icon/arrow_down.svg';
import IconArrowUp from '@/public/icons/icon/arrow_up.svg';
import IconDashboard from '@/public/icons/icon/dashboard.svg';
import IconHome from '@/public/icons/icon/home.svg';
import IconKebabHorizontal from '@/public/icons/icon/kebab_horizontal.svg';
import IconOpenInNew from '@/public/icons/icon/open_in_new_24.svg';
import { Button } from '@/shared/components/ui/button';

import { catchupParameters } from '../../../../../.storybook/catchupStoryParameters';
import ReviewNeededTag from './ReviewNeededTag';
import WikiPageHeader from './WikiPageHeader';

/** 5종 중 4종의 우측은 ⋯ 하나뿐이다. 메뉴 내용 시안이 없어 트리거만 두고 열지 않는다. */
function MoreButton({ onClick }: { onClick?: () => void }) {
  return (
    <Button variant="icon-only-gray" size="md" aria-label="더보기" onClick={onClick}>
      <IconKebabHorizontal aria-hidden className="size-6" />
    </Button>
  );
}

/**
 * 검토큐 문서 헤더의 우측 3종. 문서 넘기기 방향(∨=다음/∧=이전)은 시안에 라벨이 없어
 * 배치 순서(아래→위)로 읽은 것이다 — 디자이너 확인 대상.
 */
function ReviewQueueActions() {
  return (
    <>
      <Button variant="icon-only-gray" size="md" aria-label="다음 문서">
        <IconArrowDown aria-hidden className="size-6" />
      </Button>
      <Button variant="icon-only-gray" size="md" aria-label="이전 문서">
        <IconArrowUp aria-hidden className="size-6" />
      </Button>
      <Button variant="box-outline-gray" size="md">
        미리보기
        <IconOpenInNew aria-hidden className="size-5" />
      </Button>
    </>
  );
}

const getHeader = (canvasElement: HTMLElement) => canvasElement.querySelector('header') as HTMLElement;

// props가 variant로 갈리는 union이라 play의 `args`는 좁혀지지 않는다(main 쪽에는 breadcrumb 관련
// 필드가 없다). 캐스팅 대신 스토리 밖에 값을 두고 args와 play가 같은 것을 가리키게 한다.
const onFolderCrumbClick = fn();
const onDocumentCrumbClick = fn();
const NARROW_CURRENT_LABEL = 'Update documentation content 문서 제목이 아주 길어지는 경우의 말줄임 확인용 텍스트';

const meta = {
  title: 'Compositions/LLM Wiki/Header/WikiPageHeader',
  component: WikiPageHeader,
  tags: ['autodocs'],
  parameters: {
    ...catchupParameters({
      level: 'composition',
      domain: 'llm-wiki',
      fsdLayer: 'features',
      owner: 'feature',
      dataProfile: 'static',
      designSource: 'figma',
      figma: {
        url: 'https://www.figma.com/design/7UwupbVvmHkElmP2OBJQio/Design-System?node-id=585-7525',
        fileKey: '7UwupbVvmHkElmP2OBJQio',
        nodeId: '585:7525',
      },
      viewport: { width: 1200, height: 120 },
      states: [
        'main-dashboard',
        'main-channel',
        'detail-folder',
        'detail-document',
        'detail-review-queue',
        'long-title-narrow',
      ],
      reuseNotes: [
        'Figma `Header` 세트(585:7525)의 두 state를 그대로 옮겼다 — state=Main(17001:78508)이 variant="main", state=세부페이지_2단이상(522:2436)이 variant="detail". 검토큐(17930:57154)만 detach된 FRAME이지만 구조는 detail과 같다.',
        '리포에 같은 셸의 선례가 둘 있다: AgentStudioHeader(main, px-16)와 RagContentHeader(detail, px-6). 둘 다 h-13 · justify-between · border-b · py-2로 같고 좌우 패딩만 갈린다 — 이 컴포넌트가 그 공통부를 가진다.',
        '우측 버튼은 shared Button 재사용이다. ⋯ = icon-only-gray/md(p-1.5 + rounded-lg → 36px, Figma Icon button 585:5628과 정확히 일치), 미리보기 = box-outline-gray/md(px-2.5 py-1.5 = Figma 10/6, Box Button 636:6333).',
        'breadcrumb 마디만 Button을 쓰지 않는다. Figma는 Text Button(582:3810)의 size=large_{이전,현재}페이지인데 코드 variant text-secondary-mono에는 그 규격이 없다(lg는 17px·rounded-full, md는 Medium 15px). RagContentHeader도 같은 이유로 직접 그렸다.',
        '아이콘은 home·menu·arrow_right2를 SVG mask id(=Figma 노드 id)로 동일 확인했고, kebab_horizontal·dashboard·folder·wiki_channel·arrow_down은 path 좌표 대조로 일치를 확인했다. 신규는 arrow_up(기존에 없음)과 open_in_new_24(기존 open_in_new는 18그리드·다른 노드·path 구조 불일치 — SNB의 search_300 선례) 2개다.',
      ],
      dataNotes: [
        'breadcrumb는 전부 props 주입이고 기존 DocumentBreadcrumb 계약(kind + label)을 그대로 쓴다 — 공유 파일 llmWikiModel.ts는 건드리지 않았다.',
        '마지막 마디가 현재 페이지다. 버튼이 아니고 aria-current="page"를 갖는다 — 클릭 대상이 아니라는 사실을 시각(색)이 아니라 마크업으로도 남긴다.',
        '우측 슬롯 내용물은 전부 소비처 몫이다. ⋯ 메뉴 항목 시안이 없어 트리거만 두고 DropdownMenu를 붙이지 않았다.',
        '"검토 필요" 태그는 ReviewNeededTag로 분리했다 — 헤더는 자리(현재 마디 옆, gap 8)만 정하고 내용을 모른다.',
        '로딩·빈·에러 헤더는 만들지 않는다(시안 없음, 감사 금지 목록).',
      ],
      tokenNotes: [
        '테두리 #EAEBEC = border-line-normal-neutral, 아래 1px만(strokeWeight "0px 0px 1px").',
        'main 제목 17px #33363D = text-heading-medium + text-text-normal-normal, 아이콘 24 = size-6 · text-icon-normal-normal(AgentStudioHeader와 같은 값).',
        'detail 마디 15px SemiBold = text-heading-small. 이전 마디 #6D7882 = text-text-normal-alternative, 현재 마디 #33363D = text-text-normal-normal. 아이콘은 색 클래스를 따로 주지 않고 마디 글자색을 상속한다(currentColor).',
        '구분자 arrow_right2 20 = size-5 · text-icon-normal-neutral.',
        '마디 hover/pressed는 fill-normal-interaction-{hover,pressed}다. Figma Text Button 세트에 state 축이 있고, 같은 컴포넌트의 코드 구현인 Button text-secondary-mono가 이미 이 두 토큰을 쓴다.',
      ],
      layoutNotes: [
        '높이 52 = py 8×2 + 내용물 36. main(Icon button 36)과 detail(Text Button 36) 둘 다 같은 값이 나온다. 선례 둘도 h-13이라 그대로 못박았다.',
        '좌우 패딩은 state에 묶인 값이다 — main 64(px-16), detail 24(px-6). Figma가 그렇게 갈라 뒀고 리포 선례 둘도 같은 숫자다.',
        '폭 흡수는 좌측 하나뿐(min-w-0). 축소 순서는 현재 마디 truncate가 먼저고, 이전 마디들과 우측 액션은 shrink-0으로 고정이다 — 가로 스크롤은 넣지 않았다.',
        'Figma 검토큐 시안에서도 현재 마디만 말줄임 처리돼 있다("Update documentation con…") — 흡수 슬롯 선택의 근거다.',
        '마디 높이 36은 padding(4)+라인박스(22.5)=30.5로는 나오지 않는 Figma 고정값이라 h-9로 못박았다. hover 배경이 이 높이로 그려진다.',
      ],
    }),
  },
} satisfies Meta<typeof WikiPageHeader>;

export default meta;
type Story = StoryObj<typeof WikiPageHeader>;

/** 대시보드 17600:149328 — 아이콘 + 제목, 우측 ⋯ */
export const Dashboard: Story = {
  args: {
    variant: 'main',
    icon: <IconDashboard />,
    title: '대시보드',
    actions: <MoreButton />,
  },
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement);
    const header = getHeader(canvasElement);

    await expect(canvas.getByText('대시보드')).toBeInTheDocument();
    await expect(canvas.getByRole('button', { name: '더보기' })).toBeInTheDocument();

    // main은 좌우 64. detail(24)과 갈리는 유일한 기하라 값을 직접 잰다.
    await expect(getComputedStyle(header).paddingLeft).toBe('64px');
    await expect(header.getBoundingClientRect().height).toBe(52);

    // 아이콘 크기는 소비처가 주지 않고 헤더가 강제한다 — 5종이 흔들리지 않게.
    const icon = header.querySelector('svg') as SVGElement;
    await expect(icon.getBoundingClientRect().width).toBe(24);

    // main은 breadcrumb가 아니다. nav가 생기면 구조를 잘못 옮긴 것이다.
    await expect(canvas.queryByRole('navigation')).toBeNull();
  },
};

/** 채널 17752:45516 — 같은 main state, 아이콘만 icon/home으로 갈린다 */
export const Channel: Story = {
  args: {
    variant: 'main',
    icon: <IconHome />,
    title: '채널명',
    actions: <MoreButton />,
  },
  play: async ({ canvasElement }) => {
    await expect(within(canvasElement).getByText('채널명')).toBeInTheDocument();
    await expect(getComputedStyle(getHeader(canvasElement)).paddingLeft).toBe('64px');
  },
};

/** 폴더 17762:104786 — 채널명 > 현재페이지 2단 */
export const Folder: Story = {
  args: {
    variant: 'detail',
    breadcrumbs: [
      { kind: 'channel', label: '채널명' },
      { kind: 'document', label: '현재페이지' },
    ],
    onBreadcrumbClick: onFolderCrumbClick,
    actions: <MoreButton />,
  },
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement);
    const header = getHeader(canvasElement);

    await expect(getComputedStyle(header).paddingLeft).toBe('24px');
    await expect(header.getBoundingClientRect().height).toBe(52);

    // 이전 마디만 버튼이다. 현재 마디까지 버튼이 되면 "여기로 이동"이 두 번 생긴다.
    const channelCrumb = canvas.getByRole('button', { name: '채널명' });
    await expect(canvas.queryByRole('button', { name: '현재페이지' })).toBeNull();
    await expect(canvas.getByText('현재페이지').closest('[aria-current]')).not.toBeNull();

    // Figma Text Button은 h36 고정이다 — padding에서 파생되지 않으므로 직접 잰다.
    await expect(channelCrumb.getBoundingClientRect().height).toBe(36);

    await userEvent.click(channelCrumb);
    await expect(onFolderCrumbClick).toHaveBeenCalledWith({ kind: 'channel', label: '채널명' }, 0);
  },
};

/**
 * 문서 열람·직접 편집 17922:56420 — 채널 > 폴더 > 현재페이지 3단.
 * 이 시안의 마디에는 아이콘이 없지만, 가장 최근 시안인 검토큐(17930:57154)가 같은 자리에
 * wiki_channel·folder를 달고 있어 kind 매핑을 그쪽에 맞췄다(디자이너 확인 대상).
 */
export const Document: Story = {
  args: {
    variant: 'detail',
    breadcrumbs: [
      { kind: 'channel', label: '채널' },
      { kind: 'folder', label: '폴더' },
      { kind: 'document', label: '현재페이지' },
    ],
    onBreadcrumbClick: onDocumentCrumbClick,
    actions: <MoreButton />,
  },
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement);

    // 구분자 2개 + 마디 아이콘 2개. 3단 체인이 접히거나 join되지 않았는지 본다.
    await expect(canvas.getAllByRole('button', { name: /채널|폴더/ })).toHaveLength(2);
    await expect(canvas.getByText('현재페이지')).toBeInTheDocument();

    await userEvent.click(canvas.getByRole('button', { name: '폴더' }));
    await expect(onDocumentCrumbClick).toHaveBeenCalledWith({ kind: 'folder', label: '폴더' }, 1);
  },
};

/** 검토큐 문서 17930:57154 — 3단 + "검토 필요" 태그 + 우측 3종 */
export const ReviewQueueDocument: Story = {
  args: {
    variant: 'detail',
    breadcrumbs: [
      { kind: 'channel', label: '채널명' },
      { kind: 'folder', label: '폴더명' },
      { kind: 'document', label: 'Update documentation content' },
    ],
    onBreadcrumbClick: fn(),
    badge: <ReviewNeededTag />,
    actions: <ReviewQueueActions />,
  },
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement);

    await expect(canvas.getByText('검토 필요')).toBeInTheDocument();
    await expect(canvas.getByRole('button', { name: '다음 문서' })).toBeInTheDocument();
    await expect(canvas.getByRole('button', { name: '이전 문서' })).toBeInTheDocument();
    await expect(canvas.getByRole('button', { name: /미리보기/ })).toBeInTheDocument();

    // 태그 기하는 Figma Tag(452:2175) 값이다. shared Badge 기본은 rounded-full이라
    // tailwind-merge가 덮어쓰기를 놓치면 알약으로 조용히 되돌아간다.
    const tag = canvas.getByText('검토 필요');
    await expect(getComputedStyle(tag).borderRadius).toBe('6px');

    // 태그 아이콘은 원본 export가 stroke="#464C53"이었다. 재export로 hex가 되살아나면
    // 라이트에서는 눈에 안 띄고 다크에서만 어긋나므로 계산색이 아니라 속성을 못박는다.
    const tagIcon = tag.querySelector('svg path');
    await expect(tagIcon).toHaveAttribute('stroke', 'currentColor');

    // 배지가 있어도 헤더 높이는 52 그대로여야 한다(태그가 행을 밀지 않는다).
    await expect(getHeader(canvasElement).getBoundingClientRect().height).toBe(52);
  },
};

/**
 * 좁은 슬롯. 폭이 줄면 현재 마디만 잘리고 이전 마디·태그·우측 액션은 그대로 남아야 한다.
 * 새 상태가 아니라 검토큐와 같은 상태를 좁은 폭에서 다시 잰 것이다.
 */
export const LongTitleInNarrowSlot: Story = {
  args: {
    variant: 'detail',
    breadcrumbs: [
      { kind: 'channel', label: '채널명' },
      { kind: 'folder', label: '폴더명' },
      { kind: 'document', label: NARROW_CURRENT_LABEL },
    ],
    badge: <ReviewNeededTag />,
    actions: <ReviewQueueActions />,
  },
  decorators: [
    (Story) => (
      <div className="w-160 overflow-hidden">
        <Story />
      </div>
    ),
  ],
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement);
    const header = getHeader(canvasElement);
    const slot = canvasElement.querySelector('div.w-160') as HTMLElement;

    // 헤더가 슬롯을 넘지 않는다.
    await expect(header.getBoundingClientRect().width).toBeLessThanOrEqual(slot.getBoundingClientRect().width);
    await expect(header.scrollWidth).toBeLessThanOrEqual(header.clientWidth);

    // 현재 마디만 잘린다. 넘침 없음만으로는 부족하다 — truncate가 빠지면 줄바꿈으로 폭은
    // 지키면서 헤더 높이가 자라고, 그러면 화면 간 헤더 리듬이 어긋난다.
    const current = canvas.getByText(NARROW_CURRENT_LABEL);
    await expect(current.scrollWidth).toBeGreaterThan(current.clientWidth);
    await expect(current.getClientRects()).toHaveLength(1);
    await expect(header.getBoundingClientRect().height).toBe(52);

    // 잘리는 쪽은 현재 마디뿐이다 — 이전 마디와 우측 액션은 폭을 내주지 않는다.
    const folderCrumb = canvas.getByRole('button', { name: '폴더명' });
    await expect(folderCrumb.scrollWidth).toBeLessThanOrEqual(folderCrumb.clientWidth);
    await expect(canvas.getByRole('button', { name: /미리보기/ }).scrollWidth).toBeLessThanOrEqual(
      canvas.getByRole('button', { name: /미리보기/ }).clientWidth,
    );
  },
};
