import SideNavBar from '@/components/common/sideNavBar/SideNavBar';

export default function AfterLoginLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <div className="flex h-full">
      <aside>
        <SideNavBar />
      </aside>
      <div className="flex flex-1 flex-col">
        <main className="flex-1 overflow-auto">
          {children}
        </main>
      </div>
    </div>
  );
}