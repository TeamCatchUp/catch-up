import HomeTopNavbar from '@/components/home/topNavbar/TopNavbar';
import HowToUse from '@/components/home/cardComponents/HowToUse';
import LinkTool from '@/components/home/cardComponents/LinkTool';
<<<<<<< HEAD:src/app/page.tsx
import TaskRecentlyChecked from '@/components/home/cardComponents/TaskRecentlyChecked';
=======
import RecentlyChecked from '@/components/home/cardComponents/RecentlyChecked';
import Search from './search/page';
>>>>>>> develop:src/app/(afterLogin)/page.tsx

export default function Home() {
  return (
    <div className="bg-home-gradient flex flex-col">
      <HomeTopNavbar />
<<<<<<< HEAD:src/app/page.tsx
      {/* 검색 */}
      <div className="flex flex-col items-center gap-16 px-12 py-10">
        <TaskRecentlyChecked />
=======
      <Search />
      <div className="flex flex-col items-center gap-16 px-16 pt-10 pb-30">
        <RecentlyChecked />
>>>>>>> develop:src/app/(afterLogin)/page.tsx
        <HowToUse />
        <LinkTool />
      </div>
    </div>
  );
}
