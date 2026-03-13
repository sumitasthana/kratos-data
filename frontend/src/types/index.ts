export type ProjectStatus = "idle" | "profiling" | "generating" | "validating" | "done" | "error";
export type UseCase = "ml_training" | "analytics" | "qa_testing" | "regulatory";
export type PrivacyLevel = "none" | "no_verbatim_pii" | "k5" | "k10";
export type GenerationStatus = "idle" | "running" | "paused" | "complete" | "failed";
export type ChatRole = "user" | "agent" | "system";
export type AgentStatus = "idle" | "running" | "waiting_confirmation";
export type ConstraintSeverity = "hard" | "soft";
export type ConstraintStatus = "enforced" | "violated" | "pending";

export interface Project {
  name: string;
  status: ProjectStatus;
  currentIteration: number;
}

export interface Context {
  objective: string;
  useCase: UseCase;
  privacyLevel: PrivacyLevel;
  targetRowCounts: Record<string, number>;
  scenarioDescription: string;
  additionalConstraints: string;
}

export interface Column {
  name: string;
  type: string;
  nullable: boolean;
  description?: string;
}

export interface Table {
  name: string;
  columns: Column[];
  rowCount?: number;
  description?: string;
}

export interface Relationship {
  id: string;
  sourceTable: string;
  targetTable: string;
  sourceColumn: string;
  targetColumn: string;
  type: string;
}

export interface Schema {
  tables: Table[];
  columns: Column[];
  relationships: Relationship[];
  assumptions: string[];
  anomalies: string[];
}

export interface ColumnStats {
  columnName: string;
  dataType: string;
  nullCount: number;
  uniqueCount: number;
  min?: string | number;
  max?: string | number;
  mean?: number;
  stdDev?: number;
  distribution?: Record<string, number>;
}

export interface Profile {
  perColumnStats: ColumnStats[];
  correlations: Record<string, number>;
  anomalies: string[];
}

export interface Constraint {
  id: string;
  type: string;
  scope: string;
  severity: ConstraintSeverity;
  status: ConstraintStatus;
  description: string;
}

export interface DependencyNode {
  id: string;
  type: string;
  dependencies: string[];
}

export interface Rules {
  constraints: Constraint[];
  dependencyGraph: DependencyNode[];
}

export interface GenerationParams {
  rowCount: number;
  seed?: number;
  parallelism?: number;
  batchSize?: number;
}

export interface ValidationResult {
  id: string;
  tableName: string;
  columnName?: string;
  passed: boolean;
  message: string;
  severity: "error" | "warning" | "info";
}

export interface ViolationSummary {
  totalViolations: number;
  errorCount: number;
  warningCount: number;
  infoCount: number;
}

export interface RepairSuggestion {
  id: string;
  violationId: string;
  suggestion: string;
  priority: "high" | "medium" | "low";
}

export interface GenerationIteration {
  iterationNumber: number;
  params: GenerationParams;
  validationSummary: ViolationSummary;
  timestamp: string;
}

export interface Generation {
  plan: string;
  status: GenerationStatus;
  params: GenerationParams;
  iterations: GenerationIteration[];
}

export interface Validation {
  results: ValidationResult[];
  violationSummary: ViolationSummary;
  repairSuggestions: RepairSuggestion[];
}

export interface ChatMessage {
  id: string;
  role: ChatRole;
  content: string;
  timestamp: string;
  agentNode?: string;
}

export interface Chat {
  messages: ChatMessage[];
  agentStatus: AgentStatus;
}

export interface AppState {
  project: Project;
  context: Context;
  schema: Schema;
  profile: Profile;
  rules: Rules;
  generation: Generation;
  validation: Validation;
  chat: Chat;
}

export interface AppActions {
  setProjectStatus: (status: ProjectStatus) => void;
  setContext: (context: Partial<Context>) => void;
  setSchema: (schema: Schema) => void;
  setProfile: (profile: Profile) => void;
  setRules: (rules: Rules) => void;
  setGenerationStatus: (status: GenerationStatus) => void;
  addChatMessage: (message: ChatMessage) => void;
  setAgentStatus: (status: AgentStatus) => void;
  addIteration: (iteration: GenerationIteration) => void;
  setValidationResults: (results: ValidationResult[]) => void;
}
