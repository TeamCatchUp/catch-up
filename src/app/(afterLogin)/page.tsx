'use client';

import { useState } from 'react';
import TopNavbar from '@/components/common/topNavbar/TopNavbar';
import HowToUse from '@/components/home/cardComponents/HowToUse';
import LinkTool from '@/components/home/cardComponents/LinkTool';
import TaskRecentlyChecked from '@/components/home/cardComponents/TaskRecentlyChecked';
import Search from './search/page';
import TaskRecentlyCheckedModal from '@/components/home/modal/TaskRecentlyCheckedModal';

export default function Home() {
  const [selectedTask, setSelectedTask] = useState<TaskRecentlyCheckedCard | null>(null);

  return (
    <div className="bg-home-gradient flex flex-col">
      <TopNavbar pageType="home" />
      <Search />
      <div className="flex flex-col items-center gap-16 px-16 pt-10 pb-30">
        <TaskRecentlyChecked onClickCard={setSelectedTask} />
        <HowToUse />
        <LinkTool />
      </div>

      {selectedTask && (
        <div className="fixed inset-0 z-50 flex items-center justify-center">
          <div onClick={() => setSelectedTask(null)} className="absolute inset-0 bg-white/50" />
          <div className="relative z-10">
            <TaskRecentlyCheckedModal task={selectedTask} onClose={() => setSelectedTask(null)} />
          </div>
        </div>
      )}
    </div>
  );
}
