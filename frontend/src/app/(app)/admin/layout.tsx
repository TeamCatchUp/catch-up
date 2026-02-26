/**
 * 관리자 페이지 전용 레이아웃
 */
export default function AdminLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="flex flex-col">
      <main>{children}</main>
    </div>
  );
}
