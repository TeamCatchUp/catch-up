import { agentStudioEditorFigmaCase, agentStudioListFigmaCase } from '../cases/agentStudio.figma-case';
import type { FigmaLabCase } from '../types';

export const AGENT_STUDIO_FIGMA_LAB_CASES = [
  agentStudioListFigmaCase,
  agentStudioEditorFigmaCase,
] satisfies readonly FigmaLabCase[];
