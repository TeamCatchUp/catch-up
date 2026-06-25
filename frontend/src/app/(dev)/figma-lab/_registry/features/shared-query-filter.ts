import { documentSearchFilterRowDatePickerOpenFigmaCase } from '../cases/documentSearchFilterRowDatePickerOpen.figma-case';
import { documentSearchFilterRowEntryFigmaCase } from '../cases/documentSearchFilterRowEntry.figma-case';
import { documentSearchFilterRowResultExpandedFigmaCase } from '../cases/documentSearchFilterRowResultExpanded.figma-case';
import { documentSearchFilterRowSourceDropdownOpenFigmaCase } from '../cases/documentSearchFilterRowSourceDropdownOpen.figma-case';
import { smartFilterStatusPillFigmaCase } from '../cases/smartFilterStatusPill.figma-case';
import type { FigmaLabCase } from '../types';

export const SHARED_QUERY_FILTER_FIGMA_LAB_CASES = [
  documentSearchFilterRowEntryFigmaCase,
  documentSearchFilterRowSourceDropdownOpenFigmaCase,
  documentSearchFilterRowDatePickerOpenFigmaCase,
  documentSearchFilterRowResultExpandedFigmaCase,
  smartFilterStatusPillFigmaCase,
] satisfies readonly FigmaLabCase[];
