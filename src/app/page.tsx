import HomeTopNavbar from '@/components/home/topNavbar/TopNavbar';
import HowToUse from '@/components/home/cardComponents/HowToUse';
import LinkTool from '@/components/home/cardComponents/LinkTool';
import RecentlyChecked from '@/components/home/cardComponents/RecentlyChecked';
import Search from './search/page';

export default function Home() {
  return (
    <div className="bg-home-gradient flex flex-col">
      <HomeTopNavbar />
      <Search />
      <div className="flex flex-col items-center gap-16 px-12 py-10">
        <RecentlyChecked />
        <HowToUse />
        <LinkTool />
      </div>
    </div>
  );
}
