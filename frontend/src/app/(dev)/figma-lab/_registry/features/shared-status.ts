import {
  forbiddenStatusDarkFigmaCase,
  forbiddenStatusLightFigmaCase,
  notFoundStatusDarkFigmaCase,
  notFoundStatusLightFigmaCase,
} from '../cases/sharedStatus.figma-case';
import type { FigmaLabCase } from '../types';

export const SHARED_STATUS_FIGMA_LAB_CASES = [
  forbiddenStatusLightFigmaCase,
  forbiddenStatusDarkFigmaCase,
  notFoundStatusLightFigmaCase,
  notFoundStatusDarkFigmaCase,
] satisfies readonly FigmaLabCase[];
