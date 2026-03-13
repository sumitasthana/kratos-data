import { create } from 'zustand';
import type {
  AppState,
  AppActions,
  ProjectStatus,
  GenerationStatus,
  AgentStatus,
  ChatMessage,
  Schema,
  Profile,
  Rules,
  GenerationIteration,
  ValidationResult,
  Context,
} from '../types/index';

type AppStore = AppState & AppActions;

const initialState: AppState = {
  project: {
    name: '',
    status: 'idle',
    currentIteration: 0,
  },
  context: {
    objective: '',
    useCase: 'ml_training',
    privacyLevel: 'none',
    targetRowCounts: {},
    scenarioDescription: '',
    additionalConstraints: '',
  },
  schema: {
    tables: [],
    columns: [],
    relationships: [],
    assumptions: [],
    anomalies: [],
  },
  profile: {
    perColumnStats: [],
    correlations: {},
    anomalies: [],
  },
  rules: {
    constraints: [],
    dependencyGraph: [],
  },
  generation: {
    plan: '',
    status: 'idle',
    params: {
      rowCount: 1000,
    },
    iterations: [],
  },
  validation: {
    results: [],
    violationSummary: {
      totalViolations: 0,
      errorCount: 0,
      warningCount: 0,
      infoCount: 0,
    },
    repairSuggestions: [],
  },
  chat: {
    messages: [],
    agentStatus: 'idle',
  },
};

export const useAppStore = create<AppStore>((set) => ({
  ...initialState,

  setProjectStatus: (status: ProjectStatus) => {
    set((state) => ({
      project: {
        ...state.project,
        status,
      },
    }));
  },

  setContext: (context: Partial<Context>) => {
    set((state) => ({
      context: {
        ...state.context,
        ...context,
      },
    }));
  },

  setSchema: (schema: Schema) => {
    set(() => ({
      schema,
    }));
  },

  setProfile: (profile: Profile) => {
    set(() => ({
      profile,
    }));
  },

  setRules: (rules: Rules) => {
    set(() => ({
      rules,
    }));
  },

  setGenerationStatus: (status: GenerationStatus) => {
    set((state) => ({
      generation: {
        ...state.generation,
        status,
      },
    }));
  },

  addChatMessage: (message: ChatMessage) => {
    set((state) => ({
      chat: {
        ...state.chat,
        messages: [...state.chat.messages, message],
      },
    }));
  },

  setAgentStatus: (status: AgentStatus) => {
    set((state) => ({
      chat: {
        ...state.chat,
        agentStatus: status,
      },
    }));
  },

  addIteration: (iteration: GenerationIteration) => {
    set((state) => ({
      generation: {
        ...state.generation,
        iterations: [...state.generation.iterations, iteration],
      },
      project: {
        ...state.project,
        currentIteration: iteration.iterationNumber,
      },
    }));
  },

  setValidationResults: (results: ValidationResult[]) => {
    set((state) => ({
      validation: {
        ...state.validation,
        results,
      },
    }));
  },
}));
