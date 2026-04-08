'use client';

import { useTheme } from 'next-themes';

import { THEME_OPTIONS } from '../constants/preferencesConfig';
import SectionBar from './SectionBar';
import SettingDropdownRow from './SettingDropdownRow';

export default function DisplayModeSection() {
  const { theme, setTheme } = useTheme();

  return (
    <div className="flex flex-col">
      <SectionBar title="화면 모드" />
      <div className="px-4">
        <SettingDropdownRow
          label="화면 모드"
          description="이 기기에서 화면 테마를 선택해주세요."
          options={THEME_OPTIONS}
          value={theme ?? 'system'}
          onChange={setTheme}
        />
      </div>
    </div>
  );
}
