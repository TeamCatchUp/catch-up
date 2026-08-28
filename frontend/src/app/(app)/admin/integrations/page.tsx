import { redirect } from 'next/navigation';

/** 구 협업툴 연동 라우트 — 커넥터 연결로 이동 */
export default function AdminIntegrationsPage() {
  redirect('/admin/connectors');
}
