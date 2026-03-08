'use client';

import { useMutation, useQueryClient } from '@tanstack/react-query';
import { useRouter } from 'next/navigation';
import { useTheme } from 'next-themes';

import AdminPanelSettings from '@/public/icons/icon/admin_panel_settings.svg';
import Logout from '@/public/icons/icon/logout.svg';
import Person from '@/public/icons/icon/person.svg';
import DefaultProfile from '@/public/icons/icon/profile.svg';
import Settings from '@/public/icons/icon/settings.svg';
import {
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
} from '@/shared/components/ui/dropdown-menu';
import { Tabs, TabsList, TabsTrigger } from '@/shared/components/ui/tabs';
import { authMutations } from '@/shared/queries/auth.mutations';

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
          <span className="text-heading-small text-gray-80 truncate">{userName ?? '이름없음'}</span>
          <span className="text-body-small truncate text-gray-50">{userEmail ?? ''}</span>
        </div>
      </DropdownMenuLabel>

      {/* 메뉴 */}
      <DropdownMenuItem onSelect={() => router.push('/mypage/preferences')}>
        <Person className="text-gray-70 h-6 w-6" />
        <span>개인 맞춤 설정</span>
      </DropdownMenuItem>
      <DropdownMenuItem onSelect={(e) => e.preventDefault()}>
        <AdminPanelSettings className="text-gray-70 h-6 w-6" />
        <span>권한 관리</span>
      </DropdownMenuItem>
      <DropdownMenuItem onSelect={(e) => e.preventDefault()}>
        <Settings className="text-gray-70 h-6 w-6" />
        <span>설정</span>
      </DropdownMenuItem>

      {/* 라이트/다크 모드 토글 */}
      <div className="px-1 py-0.5">
        <Tabs value={theme} onValueChange={setTheme}>
          <TabsList className="w-full">
            <TabsTrigger value="light" className="flex-1">
              라이트 모드
            </TabsTrigger>
            <TabsTrigger value="dark" className="flex-1">
              다크 모드
            </TabsTrigger>
          </TabsList>
        </Tabs>
      </div>

      <DropdownMenuSeparator />

      {/* 로그아웃 */}
      <DropdownMenuItem onSelect={() => logoutMutation.mutate()}>
        <Logout className="text-gray-70 h-6 w-6" />
        <span>로그아웃</span>
      </DropdownMenuItem>
    </DropdownMenuContent>
  );
}
