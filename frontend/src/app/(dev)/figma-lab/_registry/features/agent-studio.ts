import {
  agentStudioEditorFigmaCase,
  agentStudioListFigmaCase,
  agentStudioListLoadingFigmaCase,
} from '../cases/agentStudio.figma-case';
import type { FigmaLabCase } from '../types';

export const AGENT_STUDIO_FIGMA_LAB_CASES = [
  agentStudioListFigmaCase,
  agentStudioListLoadingFigmaCase,
  agentStudioEditorFigmaCase,
] satisfies readonly FigmaLabCase[];
