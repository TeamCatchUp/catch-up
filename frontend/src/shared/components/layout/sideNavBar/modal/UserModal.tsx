'use client';

import { useMutation, useQueryClient } from '@tanstack/react-query';
import { useRouter } from 'next/navigation';
import { useTheme } from 'next-themes';

import AdminPanelSettings from '@/public/icons/icon/admin_panel_settings.svg';
import ArrowDown from '@/public/icons/icon/arrow_down.svg';
import Contrast from '@/public/icons/icon/contrast.svg';
import DarkMode from '@/public/icons/icon/dark_mode.svg';
import LightMode from '@/public/icons/icon/light_mode.svg';
import Logout from '@/public/icons/icon/logout.svg';
import Person from '@/public/icons/icon/person.svg';
import DefaultProfile from '@/public/icons/icon/profile.svg';
import Screen from '@/public/icons/icon/screen.svg';
import {
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuSub,
  DropdownMenuSubContent,
  DropdownMenuSubTrigger,
} from '@/shared/components/ui/dropdown-menu';
import { authMutations } from '@/shared/queries/auth.mutations';

const THEME_LABELS: Record<string, string> = {
  system: '시스템 (자동)',
  light: '라이트',
  dark: '다크',
};

interface UserMenuContentProps {
  userName?: string;
  userEmail?: string;
}

/**
 * 사용자 드롭다운 메뉴 내용을 렌더링
 * 로그아웃, 개인 설정 이동 등 계정 액션을 제공
 */
export function UserMenuContent({ userName, userEmail }: UserMenuContentProps) {
  const router = useRouter();
  const queryClient = useQueryClient();
  const { theme, setTheme } = useTheme();

  const logoutMutation = useMutation({
    ...authMutations.logout(),
    onSuccess: () => {
      queryClient.clear();
      window.location.href = '/login';
    },
  });

  return (
    <DropdownMenuContent
      side="top"
      align="start"
      sideOffset={8}
      className="w-62.5"
      onCloseAutoFocus={(e) => e.preventDefault()}
    >
      {/* 프로필 헤더 */}
      <DropdownMenuLabel className="flex h-12 items-center gap-4 px-1 py-0">
        <DefaultProfile className="h-10 w-10 shrink-0" />
        <div className="relative top-px flex min-w-0 flex-col">
          <span className="text-heading-small text-content-normal truncate">{userName ?? '이름없음'}</span>
          <span className="text-body-small truncate text-content-alternative">{userEmail ?? ''}</span>
        </div>
      </DropdownMenuLabel>

      {/* 메뉴 */}
      <DropdownMenuItem onSelect={() => router.push('/mypage/preferences')}>
        <Person className="text-icon-normal size-6" />
        <span>개인 맞춤 설정</span>
      </DropdownMenuItem>
      <DropdownMenuItem onSelect={(e) => e.preventDefault()}>
        <AdminPanelSettings className="text-icon-normal size-6" />
        <span>권한 관리</span>
      </DropdownMenuItem>

      {/* 화면 모드 서브메뉴 */}
      <DropdownMenuSub>
        <DropdownMenuSubTrigger>
          <Contrast className="text-icon-normal size-6" />
          <span className="flex-1">화면 모드</span>
          <span className="text-body-xsmall text-content-alternative">{THEME_LABELS[theme ?? 'system']}</span>
          <ArrowDown className="text-icon-normal size-6" />
        </DropdownMenuSubTrigger>
        <DropdownMenuSubContent>
          <DropdownMenuItem onSelect={() => setTheme('system')}>
            <Screen className="text-icon-normal size-6" />
            <span>시스템 모드</span>
          </DropdownMenuItem>
          <DropdownMenuItem onSelect={() => setTheme('light')}>
            <LightMode className="text-icon-normal size-6" />
            <span>라이트 모드</span>
          </DropdownMenuItem>
          <DropdownMenuItem onSelect={() => setTheme('dark')}>
            <DarkMode className="text-icon-normal size-6" />
            <span>다크 모드</span>
          </DropdownMenuItem>
        </DropdownMenuSubContent>
      </DropdownMenuSub>

      <DropdownMenuSeparator />

      {/* 로그아웃 */}
      <DropdownMenuItem onSelect={() => logoutMutation.mutate()}>
        <Logout className="text-icon-normal size-6" />
        <span>로그아웃</span>
      </DropdownMenuItem>
    </DropdownMenuContent>
  );
}
