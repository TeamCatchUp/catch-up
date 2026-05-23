# `(dev)` Route Group — 원문 패널 갤러리

## 무엇인가

`/original-panel` 은 ChannelTalk user_chat 원문 패널 컴포넌트의 갤러리 페이지.
**Storybook 대용**으로, 각 컴포넌트의 모든 상태/케이스를 fixture 로 렌더해
디자이너·개발자가 시각적으로 확인할 수 있게 한다.

**의도적으로 production 에도 노출된다.** 정식 Storybook 도입까지의 임시 조치 —
PII 없음, API 호출 없음, 번들 영향 미미.

## 언제 제거하나

- 정식 Storybook (또는 다른 component dev environment) 이 도입되고 이 갤러리의
  케이스가 그쪽으로 이관된 시점.
- `/original-panel` 이 어떤 환경에서도 접근 가능할 필요가 없다고 결정된 시점.

## 어떻게 제거하나

```bash
# 1. (dev) route group 전체 삭제 — 갤러리 코드가 모두 여기 안에 있음.
rm -rf frontend/src/app/(dev)/

# 2. fixture 가 다른 곳에서도 import 되는지 확인.
grep -rln "__fixtures__/originalContent.fixtures" frontend/src

# 3a. 매치 0건 → fixture 디렉터리도 함께 삭제.
rm -rf frontend/src/features/hybrid-search/components/original/__fixtures__/

# 3b. 매치 있음 → fixture 는 두고 (테스트 등에서 사용 중), (dev) 만 삭제.

# 4. 빌드·테스트 통과 확인.
cd frontend && npm run build && npm test
```

## 삭제 후 남는 것 (건드리지 않음)

- `frontend/src/features/hybrid-search/components/original/` — 실제 feature
  컴포넌트들. `/hybrid-search` 페이지가 사용 중이므로 유지.
- API 타입 (`originalApi.ts`), queries (`originalContent.queries.ts`), hook
  (`useOriginalContent.ts`) — 모두 유지.

삭제 대상: 갤러리 shell (`(dev)/`) + (선택적으로) fixtures 뿐.

## 현재 구조

```
frontend/src/app/(dev)/
├── README.md                       이 파일
├── layout.tsx                      dev shell (production gate 없음 — 의도적)
└── original-panel/
    ├── layout.tsx                  sidebar + main flex shell
    ├── page.tsx                    타일 그리드 index
    ├── [slug]/page.tsx             동적 라우트 (컴포넌트별 페이지)
    ├── _registry/
    │   ├── entries.ts              16개 entry 메타·그룹
    │   └── render.tsx              slug → cases (client component)
    └── _components/
        ├── Sidebar.tsx · SidebarLink.tsx
        └── Case.tsx · PanelWidth.tsx · PanelFrame.tsx
```

모두 이 디렉터리 트리에 self-contained.

## 다시 production 비공개로 돌리고 싶을 때

`(dev)/layout.tsx` 에 다음 한 줄 추가:

```ts
import { notFound } from 'next/navigation';

export default function DevLayout({ children }: { children: React.ReactNode }) {
  if (process.env.NODE_ENV === 'production') notFound();
  return <div className="bg-fill-normal min-h-screen">{children}</div>;
}
```
