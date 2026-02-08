'use client';

import { useEffect,useRef, useState } from 'react';
import clsx from 'clsx';

import ArrowLeft from '/public/icons/icon/arrow_left2.svg';
import ArrowRight from '/public/icons/icon/arrow_right2.svg';
import Lock from '/public/icons/icon/lock_filled.svg';

type TabType = 'info' | 'files' | 'wiki' | 'url' | 'comments' | 'notion' | 'slack';

interface Tab {
  id: TabType;
  label: string;
  count: number;
  locked: boolean;
}

interface DetailTabNavProps {
  tabs: Tab[];
  activeTab: TabType;
  onChange: (tab: TabType) => void;
}

const DetailTabNav = ({ tabs, activeTab, onChange }: DetailTabNavProps) => {
  const scrollRef = useRef<HTMLDivElement>(null);

  const [canScrollLeft, setCanScrollLeft] = useState(false);
  const [canScrollRight, setCanScrollRight] = useState(false);
  const [hovered, setHovered] = useState(false);

  const checkScroll = () => {
    const el = scrollRef.current;
    if (!el) return;

    setCanScrollLeft(el.scrollLeft > 0);
    setCanScrollRight(Math.ceil(el.scrollLeft + el.clientWidth) < el.scrollWidth - 1); // 보정값
  };

  const scrollByAmount = (amount: number) => {
    scrollRef.current?.scrollBy({
      left: amount,
      behavior: 'smooth',
    });
  };

  useEffect(() => {
    checkScroll();
  }, [tabs]);

  return (
    <div onMouseEnter={() => setHovered(true)} onMouseLeave={() => setHovered(false)} className="relative">
      {/* option bar */}
      <div ref={scrollRef} onScroll={checkScroll} className="mt-3.5 flex h-12 gap-5 overflow-x-auto">
        {tabs.map((tab) => (
          <>
            <button
              key={tab.id}
              onClick={() => !tab.locked && onChange(tab.id)}
              className={clsx(
                'relative flex shrink-0 items-center justify-center gap-1.5',
                tab.locked ? '' : 'cursor-pointer',
              )}
            >
              <span
                className={clsx(
                  'text-heading-small relative',
                  tab.locked ? 'text-gray-30' : activeTab === tab.id ? 'text-blue-55' : 'text-gray-50',
                )}
              >
                {tab.label}
              </span>

              {tab.locked ? (
                <Lock className="relative bottom-px h-3.5 w-3.5 text-gray-50" />
              ) : (
                tab.count > 0 && (
                  <span
                    className={clsx(
                      'text-body-xsmall rounded-md2 flex h-5 w-5 items-center justify-center text-center',
                      activeTab === tab.id ? 'bg-blue-50 text-white' : 'bg-neutral-3 text-gray-50',
                    )}
                  >
                    {tab.count}
                  </span>
                )
              )}
              {activeTab === tab.id && !tab.locked && (
                <div className="bg-blue-45 absolute right-0 bottom-1.5 left-0 z-50 h-0.5" />
              )}
            </button>
            <div className="bg-neutral-3 absolute right-0 bottom-1.5 left-0 h-px" />
          </>
        ))}
      </div>

      {/* < 버튼 */}
      {hovered && canScrollLeft && (
        <button
          onClick={() => scrollByAmount(-200)}
          className="box-button-outline-gray rounded-md2! absolute top-1/2 left-0 z-10 flex h-7.5 w-7.5 -translate-y-1/2 cursor-pointer items-center justify-center"
        >
          <ArrowLeft className="text-gray-70 h-5 w-5" />
        </button>
      )}
      {/* > 버튼 */}
      {hovered && canScrollRight && (
        <button
          onClick={() => scrollByAmount(200)}
          className="box-button-outline-gray rounded-md2! absolute top-1/2 right-0 z-10 flex h-7.5 w-7.5 -translate-y-1/2 cursor-pointer items-center justify-center"
        >
          <ArrowRight className="text-gray-70 h-5 w-5" />
        </button>
      )}
    </div>
  );
};

export default DetailTabNav;
