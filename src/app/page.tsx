import HomeTopNavbar from '@/components/home/topNavbar/TopNavbar';
import HowToUse from '@/components/home/cardComponents/HowToUse';
import LinkTool from '@/components/home/cardComponents/LinkTool';

export default function Home() {
  return (
    <div className="flex flex-col">
      <HomeTopNavbar />
      {/* 검색 */}
      <div className="flex flex-col items-center gap-16 px-12 py-10">
        <HowToUse />
        <LinkTool />
      </div>
    </div>
  );
}
