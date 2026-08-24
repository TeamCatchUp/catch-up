import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { http, HttpResponse } from 'msw';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { toast } from '@/shared/components/ui/toast';
import { TooltipProvider } from '@/shared/components/ui/tooltip';
import { server } from '@/test/msw/server';

import WikiSideNavContainer from './WikiSideNavContainer';

const mockPush = vi.hoisted(() => vi.fn());

vi.mock('next/navigation', () => ({
  usePathname: () => '/llm-wiki',
  useRouter: () => ({ push: mockPush }),
}));

const mockSidebarState = {
  isSidebarOpen: true,
  lastSettingsPath: '/mypage/profile',
  setActivePanel: vi.fn(),
  setSidebarOpen: vi.fn(),
};

vi.mock('@/shared/store/sidebarStore', () => ({
  useSidebarStore: Object.assign(
    (selector?: (s: typeof mockSidebarState) => unknown) => (selector ? selector(mockSidebarState) : mockSidebarState),
    { getState: () => mockSidebarState },
  ),
}));

vi.mock('@/shared/store/userStore', () => ({
  useUserStore: (selector: (s: { user: { name: string; email: string } }) => unknown) =>
    selector({ user: { name: '팀원G', email: 'teamlead@catchup.com' } }),
}));

vi.mock('@/shared/components/layout/sideNavBar/modal/UserModal', () => ({ UserMenuContent: () => null }));
vi.mock('@/shared/components/ui/toast', () => ({ toast: vi.fn() }));

const CHANNEL_LABEL = '채널 하나';
const FOLDER_LABEL = '폴더 하나';
const DOCUMENT_LABEL = '문서 하나';
const OTHER_CHANNEL_LABEL = '다른 채널';
const OTHER_FOLDER_LABEL = '남의 폴더';

const folderDto = (id: string, name: string, channelId: string) => ({
  id,
  name,
  channel_id: channelId,
  created_at: '2026-08-19T00:00:00Z',
  created_by: { user_id: 7, display_name: '팀원F', profile_image_url: null },
  last_activity_at: '2026-08-19T00:00:00Z',
});

// 두 번째 채널은 옮기기 대상이 문서의 채널로 한정되는지 보는 대조군이다
const channelResponse = () => ({
  channels: [
    {
      id: 'ch-1',
      name: CHANNEL_LABEL,
      workspace_id: 1,
      is_admin: true,
      document_count: 1,
      folders: [folderDto('fd-1', FOLDER_LABEL, 'ch-1')],
      purpose_presets: [],
      definitions: [],
    },
    {
      id: 'ch-2',
      name: OTHER_CHANNEL_LABEL,
      workspace_id: 1,
      is_admin: false,
      document_count: 0,
      folders: [folderDto('fd-9', OTHER_FOLDER_LABEL, 'ch-2')],
      purpose_presets: [],
      definitions: [],
    },
  ],
});

const artifactResponse = () => ({
  items: [
    {
      artifact_id: 'art-1',
      kind: 'faq',
      title: DOCUMENT_LABEL,
      channel_id: 'ch-1',
      folder_id: null,
      created_at: '2026-08-19T00:00:00Z',
      last_activity_at: '2026-08-19T00:00:00Z',
      status: 'published',
      pending_proposal_count: 0,
      latest_revision: null,
      owners: [],
      is_favorite: false,
      last_edited_by: { user_id: 7, display_name: '팀원F', profile_image_url: null },
      last_edited_at: '2026-08-19T00:00:00Z',
    },
  ],
  total: 1,
  limit: 200,
  offset: 0,
});

/** 요청 하나의 경로·메서드·본문. 쓰기가 실제로 어디로 갔는지 이 기록으로 본다 */
interface RecordedWrite {
  method: string;
  path: string;
  body: unknown;
}

let writes: RecordedWrite[] = [];
let channelListCallCount = 0;
let favoriteListCallCount = 0;

/** 링크 복사가 무엇을 넘겼는지 보는 자리. userEvent.setup()이 심는 클립보드 스텁을 뒤에서 덮는다 */
const writeText = vi.fn<(text: string) => Promise<void>>();
const stubClipboard = () => Object.defineProperty(navigator, 'clipboard', { value: { writeText }, configurable: true });

const recordWrite = async (request: Request): Promise<RecordedWrite> => ({
  method: request.method,
  path: new URL(request.url).pathname,
  body: request.body ? await request.clone().json() : null,
});

beforeEach(() => {
  writes = [];
  channelListCallCount = 0;
  favoriteListCallCount = 0;
  writeText.mockResolvedValue(undefined);

  server.use(
    http.get('/api/v1/auth/me', () =>
      HttpResponse.json({ name: '팀원G', email: 'teamlead@catchup.com', role: 'admin', status: 'active' }),
    ),
    http.get('/api/v1/wiki/channels', () => {
      channelListCallCount += 1;
      return HttpResponse.json(channelResponse());
    }),
    http.get('/api/v1/wiki/favorites', () => {
      favoriteListCallCount += 1;
      return HttpResponse.json({ items: [] });
    }),
    http.get('/api/v1/wiki/artifacts', () => HttpResponse.json(artifactResponse())),
    http.put('/api/v1/wiki/favorites/:artifactId', async ({ request }) => {
      writes.push(await recordWrite(request));
      return HttpResponse.json({ artifact_id: 'art-1', is_favorite: true });
    }),
    http.delete('/api/v1/wiki/favorites/:artifactId', async ({ request }) => {
      writes.push(await recordWrite(request));
      return new HttpResponse(null, { status: 204 });
    }),
    http.patch('/api/v1/wiki/channels/:channelId', async ({ request }) => {
      writes.push(await recordWrite(request));
      return HttpResponse.json({ id: 'ch-1', name: '새 채널 이름', workspace_id: 1 });
    }),
    http.patch('/api/v1/wiki/channels/:channelId/folders/:folderId', async ({ request }) => {
      writes.push(await recordWrite(request));
      return HttpResponse.json({ id: 'fd-1', name: '새 폴더 이름', channel_id: 'ch-1' });
    }),
    http.post('/api/v1/wiki/channels/:channelId/folders', async ({ request }) => {
      writes.push(await recordWrite(request));
      return HttpResponse.json({ id: 'fd-2', name: '장애 대응', channel_id: 'ch-1' }, { status: 201 });
    }),
    http.patch('/api/v1/wiki/artifacts/:artifactId', async ({ request }) => {
      writes.push(await recordWrite(request));
      return HttpResponse.json({ artifact_id: 'art-1', folder_id: 'fd-1' });
    }),
  );
});

afterEach(() => {
  vi.clearAllMocks();
});

function renderContainer() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  return render(
    <QueryClientProvider client={queryClient}>
      <TooltipProvider>
        <WikiSideNavContainer />
      </TooltipProvider>
    </QueryClientProvider>,
  );
}

/** 트리는 접힌 채로 서므로 문서 행을 보려면 채널을 펼쳐 문서 목록을 받아온다 */
const expandChannel = async (user: ReturnType<typeof userEvent.setup>) => {
  await user.click(await screen.findByRole('button', { name: `${CHANNEL_LABEL} 펼치기` }));
  return screen.findByRole('button', { name: `${DOCUMENT_LABEL} 추가 작업` });
};

const rename = async (user: ReturnType<typeof userEvent.setup>, nextName: string) => {
  await user.click(screen.getByRole('button', { name: '이름 바꾸기' }));
  const input = screen.getByRole('textbox', { name: '이름 바꾸기' });
  await user.clear(input);
  await user.type(input, `${nextName}{Enter}`);
};

describe('WikiSideNavContainer 쓰기 배선', () => {
  it('문서 케밥의 즐겨찾기 등록이 그 문서 경로로 PUT을 보낸다', async () => {
    const user = userEvent.setup();
    renderContainer();

    await user.click(await expandChannel(user));
    await user.click(screen.getByRole('button', { name: '즐겨찾기에 추가' }));

    await waitFor(() => expect(writes).toEqual([{ method: 'PUT', path: '/api/v1/wiki/favorites/art-1', body: null }]));
    // 즐겨찾기 섹션과 문서 행의 별 상태가 함께 바뀌어 위키 뿌리를 다시 읽는다
    await waitFor(() => expect(favoriteListCallCount).toBeGreaterThan(1));
  });

  it('즐겨찾기된 문서의 해제는 같은 경로로 DELETE를 보낸다', async () => {
    server.use(
      http.get('/api/v1/wiki/artifacts', () =>
        HttpResponse.json({ ...artifactResponse(), items: [{ ...artifactResponse().items[0], is_favorite: true }] }),
      ),
    );
    const user = userEvent.setup();
    renderContainer();

    await user.click(await expandChannel(user));
    await user.click(screen.getByRole('button', { name: '즐겨찾기 해제' }));

    await waitFor(() =>
      expect(writes).toEqual([{ method: 'DELETE', path: '/api/v1/wiki/favorites/art-1', body: null }]),
    );
  });

  it('채널 이름 바꾸기가 채널 경로로 PATCH를 보내고 목록을 다시 읽는다', async () => {
    const user = userEvent.setup();
    renderContainer();

    await user.click((await screen.findAllByRole('button', { name: `${CHANNEL_LABEL} 추가 작업` }))[0]);
    await rename(user, '새 채널 이름');

    await waitFor(() =>
      expect(writes).toEqual([{ method: 'PATCH', path: '/api/v1/wiki/channels/ch-1', body: { name: '새 채널 이름' } }]),
    );
    await waitFor(() => expect(channelListCallCount).toBeGreaterThan(1));
  });

  it('폴더 이름 바꾸기는 소속 채널이 실린 경로로 PATCH를 보낸다', async () => {
    const user = userEvent.setup();
    renderContainer();

    await user.click(await screen.findByRole('button', { name: `${CHANNEL_LABEL} 펼치기` }));
    await user.click(await screen.findByRole('button', { name: `${FOLDER_LABEL} 추가 작업` }));
    await rename(user, '새 폴더 이름');

    await waitFor(() =>
      expect(writes).toEqual([
        { method: 'PATCH', path: '/api/v1/wiki/channels/ch-1/folders/fd-1', body: { name: '새 폴더 이름' } },
      ]),
    );
  });

  it('하위 폴더 추가가 채널 폴더 경로로 POST를 보내고 목록을 다시 읽는다', async () => {
    const user = userEvent.setup();
    renderContainer();

    await user.click(await screen.findByRole('button', { name: `${CHANNEL_LABEL} 하위 페이지 추가` }));
    await user.click(screen.getByRole('button', { name: '폴더' }));
    await user.type(screen.getByRole('textbox', { name: '폴더 이름' }), '장애 대응{Enter}');

    await waitFor(() =>
      expect(writes).toEqual([
        { method: 'POST', path: '/api/v1/wiki/channels/ch-1/folders', body: { name: '장애 대응' } },
      ]),
    );
    await waitFor(() => expect(channelListCallCount).toBeGreaterThan(1));
  });

  it('링크 복사는 현재 오리진에 노드 경로를 붙여 클립보드에 넣는다', async () => {
    const user = userEvent.setup();
    stubClipboard();
    renderContainer();

    await user.click((await screen.findAllByRole('button', { name: `${CHANNEL_LABEL} 추가 작업` }))[0]);
    await user.click(screen.getByRole('button', { name: '링크 복사' }));

    await waitFor(() => expect(writeText).toHaveBeenCalledWith(`${window.location.origin}/llm-wiki/channel/ch-1`));
    await waitFor(() => expect(toast).toHaveBeenCalledWith('링크가 복사되었습니다.'));
    // 읽기 액션이라 서버로는 아무것도 나가지 않는다
    expect(writes).toEqual([]);
  });

  it('클립보드 권한이 막히면 실패 문구를 띄운다', async () => {
    const user = userEvent.setup();
    stubClipboard();
    writeText.mockRejectedValue(new Error('denied'));
    renderContainer();

    await user.click((await screen.findAllByRole('button', { name: `${CHANNEL_LABEL} 추가 작업` }))[0]);
    await user.click(screen.getByRole('button', { name: '링크 복사' }));

    await waitFor(() => expect(toast).toHaveBeenCalledWith('복사에 실패했습니다.'));
  });

  it('위키 섹션의 채널 추가는 온보딩으로 보낸다', async () => {
    const user = userEvent.setup();
    renderContainer();

    await user.click(await screen.findByRole('button', { name: '추가하기' }));
    await user.click(screen.getByRole('button', { name: '채널' }));

    expect(mockPush).toHaveBeenCalledWith('/llm-wiki/onboarding');
  });

  /** 옮기기 → 대상 패널까지 여는 공통 경로. 패널은 문서의 채널이 펼쳐진 채 선다 */
  const openMovePicker = async (user: ReturnType<typeof userEvent.setup>) => {
    await user.click(await expandChannel(user));
    await user.click(screen.getByRole('button', { name: '옮기기' }));
    return within(screen.getByTestId('move-target-picker'));
  };

  it('옮기기의 폴더 선택이 그 문서 경로로 folder_id PATCH를 보낸다', async () => {
    const user = userEvent.setup();
    renderContainer();

    const picker = await openMovePicker(user);
    await user.click(picker.getByRole('button', { name: FOLDER_LABEL }));

    // 고른 즉시 패널이 닫힌다 — 응답을 기다리지 않는다
    expect(screen.queryByTestId('move-target-picker')).toBeNull();
    await waitFor(() =>
      expect(writes).toEqual([{ method: 'PATCH', path: '/api/v1/wiki/artifacts/art-1', body: { folder_id: 'fd-1' } }]),
    );
    // 채널 트리와 문서 목록이 함께 바뀌어 위키 뿌리를 다시 읽는다
    await waitFor(() => expect(channelListCallCount).toBeGreaterThan(1));
    // 완료 토스트는 파일명과 옮긴 위치를 함께 말한다
    await waitFor(() =>
      expect(toast).toHaveBeenCalledWith(
        `${DOCUMENT_LABEL}의 옮긴 위치는 ${FOLDER_LABEL} 입니다.`,
        expect.objectContaining({ action: expect.objectContaining({ label: '이동' }) }),
      ),
    );
  });

  it('폴더 속 문서에서 채널 행을 고르면 folder_id가 null로 나간다 — 채널 루트로 꺼낸다', async () => {
    server.use(
      http.get('/api/v1/wiki/artifacts', () =>
        HttpResponse.json({ ...artifactResponse(), items: [{ ...artifactResponse().items[0], folder_id: 'fd-1' }] }),
      ),
    );
    const user = userEvent.setup();
    renderContainer();

    // 폴더 속 문서라 트리에서 폴더까지 펼쳐야 케밥이 보인다
    await user.click(await screen.findByRole('button', { name: `${CHANNEL_LABEL} 펼치기` }));
    await user.click(await screen.findByRole('button', { name: `${FOLDER_LABEL} 펼치기` }));
    await user.click(await screen.findByRole('button', { name: `${DOCUMENT_LABEL} 추가 작업` }));
    await user.click(screen.getByRole('button', { name: '옮기기' }));
    const picker = within(screen.getByTestId('move-target-picker'));

    // 현재 폴더 행은 잠기고 채널 행이 열려 있다
    expect(picker.getByRole('button', { name: FOLDER_LABEL })).toBeDisabled();
    await user.click(picker.getByRole('button', { name: CHANNEL_LABEL }));

    await waitFor(() =>
      expect(writes).toEqual([{ method: 'PATCH', path: '/api/v1/wiki/artifacts/art-1', body: { folder_id: null } }]),
    );
  });

  it('대상 목록은 그 문서의 채널 하나로 한정된다 — 서버가 같은 채널 안 이동만 받는다', async () => {
    const user = userEvent.setup();
    renderContainer();

    const picker = await openMovePicker(user);

    expect(picker.getByRole('button', { name: FOLDER_LABEL })).toBeInTheDocument();
    expect(picker.queryByRole('button', { name: OTHER_CHANNEL_LABEL })).toBeNull();
    expect(picker.queryByRole('button', { name: OTHER_FOLDER_LABEL })).toBeNull();
  });

  it('채널 루트의 문서는 채널 행이 잠긴다 — 제자리 이동을 만들지 않는다', async () => {
    const user = userEvent.setup();
    renderContainer();

    const picker = await openMovePicker(user);

    expect(picker.getByRole('button', { name: CHANNEL_LABEL })).toBeDisabled();
    expect(picker.getByRole('button', { name: FOLDER_LABEL })).toBeEnabled();
  });

  it('토스트의 이동 버튼은 옮긴 자리로 보낸다', async () => {
    const user = userEvent.setup();
    renderContainer();

    const picker = await openMovePicker(user);
    await user.click(picker.getByRole('button', { name: FOLDER_LABEL }));

    await waitFor(() => expect(toast).toHaveBeenCalled());
    const options = vi.mocked(toast).mock.calls.at(-1)?.[1] as unknown as { action: { onClick: () => void } };
    options.action.onClick();

    expect(mockPush).toHaveBeenCalledWith('/llm-wiki/folder/fd-1');
  });

  it('검수 자격이 없으면 서버 거절 문구를 띄운다 — 항목을 숨기지 않는다', async () => {
    server.use(
      http.patch('/api/v1/wiki/artifacts/:artifactId', () =>
        HttpResponse.json(
          { detail: { code: 'NOT_DOCUMENT_REVIEWER', message: '이 문서를 옮길 권한이 없습니다.' } },
          { status: 403 },
        ),
      ),
    );
    const user = userEvent.setup();
    renderContainer();

    const picker = await openMovePicker(user);
    await user.click(picker.getByRole('button', { name: FOLDER_LABEL }));

    await waitFor(() => expect(toast).toHaveBeenCalledWith('이 문서를 옮길 권한이 없습니다.'));
  });

  it('이름 중복 409는 서버 문구를 토스트로 띄운다', async () => {
    server.use(
      http.patch('/api/v1/wiki/channels/:channelId', () =>
        HttpResponse.json(
          { detail: { code: 'CHANNEL_NAME_TAKEN', message: '이미 사용 중인 채널 이름입니다.' } },
          { status: 409 },
        ),
      ),
    );
    const user = userEvent.setup();
    renderContainer();

    await user.click((await screen.findAllByRole('button', { name: `${CHANNEL_LABEL} 추가 작업` }))[0]);
    await rename(user, '중복 이름');

    await waitFor(() => expect(toast).toHaveBeenCalledWith('이미 사용 중인 채널 이름입니다.'));
  });
});
