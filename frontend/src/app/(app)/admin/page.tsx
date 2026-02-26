import { redirect } from 'next/navigation';

/**
 * `/admin` 진입 시 기본 관리자 페이지로 리다이렉트
 */
export default function AdminPage() {
  redirect('/admin/members');
}
