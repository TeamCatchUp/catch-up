import Link from 'next/link';
import Home from '@/assets/svgs/navbar/home.svg';
import Kebeb_2 from '@/assets/svgs/navbar/kebeb_2.svg';

const TopNavbar = () => {
  return (
    <nav className="border-neutral-3 h-full w-full border-b">
      <div className="flex justify-between px-10 py-2">
        <div className="flex items-center justify-center">
          <Link href="/">
            <button className="flex cursor-pointer gap-2">
              <Home className="h-6 w-6" />
              <span className="text-heading-medium">홈</span>
            </button>
          </Link>
        </div>
        <div className="flex items-center justify-center gap-2">
          <button className="text-body-small active:border-neutral-5 active:bg-neutral-3 hover:border-neutral-4 hover:bg-neutral-2 border-neutral-3 cursor-pointer rounded-lg border px-2.5 py-1.5 transition-colors">
            공유
          </button>
          <button className="border-neutral-3 hover:border-neutral-4 active:border-neutral-5 active:bg-neutral-3 hover:bg-neutral-2 cursor-pointer rounded-lg border px-1.5 py-1.5 transition-colors">
            <Kebeb_2 className="h-6 w-6" />
          </button>
        </div>
      </div>
    </nav>
  );
};

export default TopNavbar;
