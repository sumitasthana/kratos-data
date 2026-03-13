# Zustand Store Definition

**Commit**: `388f38b` - Add complete Zustand store definition with all state slices and typed actions

## Overview

Complete TypeScript-first Zustand store implementation for the synth-data-studio frontend. This is a pure state management layer with no UI components or backend connections.

## Architecture

### State Slices

The store is organized into 8 independent state slices:

#### 1. **Project** (`project`)
Tracks the overall project metadata and status.
- `name: string` - Project name
- `status: ProjectStatus` - Current project status
  - Values: `"idle" | "profiling" | "generating" | "validating" | "done" | "error"`
- `currentIteration: number` - Current generation iteration number

#### 2. **Context** (`context`)
Stores user-provided context and requirements for data generation.
- `objective: string` - Project objective
- `useCase: UseCase` - Type of use case
  - Values: `"ml_training" | "analytics" | "qa_testing" | "regulatory"`
- `privacyLevel: PrivacyLevel` - Privacy requirements
  - Values: `"none" | "no_verbatim_pii" | "k5" | "k10"`
- `targetRowCounts: Record<string, number>` - Target row counts per table
- `scenarioDescription: string` - Detailed scenario description
- `additionalConstraints: string` - Additional constraints and requirements

#### 3. **Schema** (`schema`)
Defines the database schema structure.
- `tables: Table[]` - Array of table definitions
- `columns: Column[]` - Array of column definitions
- `relationships: Relationship[]` - Foreign key relationships
- `assumptions: string[]` - Schema assumptions
- `anomalies: string[]` - Known anomalies in the schema

#### 4. **Profile** (`profile`)
Statistical profile of the source data.
- `perColumnStats: ColumnStats[]` - Per-column statistics
- `correlations: Record<string, number>` - Column correlations
- `anomalies: string[]` - Detected anomalies

#### 5. **Rules** (`rules`)
Business rules and constraints for generation.
- `constraints: Constraint[]` - Array of constraints
  - Each constraint has: `id`, `type`, `scope`, `severity` ("hard" | "soft"), `status` ("enforced" | "violated" | "pending"), `description`
- `dependencyGraph: DependencyNode[]` - Dependency graph for constraints

#### 6. **Generation** (`generation`)
Tracks the data generation process.
- `plan: string` - Generation plan description
- `status: GenerationStatus` - Current generation status
  - Values: `"idle" | "running" | "paused" | "complete" | "failed"`
- `params: GenerationParams` - Generation parameters
  - `rowCount: number` - Target row count
  - `seed?: number` - Random seed (optional)
  - `parallelism?: number` - Parallelism level (optional)
  - `batchSize?: number` - Batch size (optional)
- `iterations: GenerationIteration[]` - Array of completed iterations

#### 7. **Validation** (`validation`)
Stores validation results and repair suggestions.
- `results: ValidationResult[]` - Array of validation results
- `violationSummary: ViolationSummary` - Summary of violations
  - `totalViolations: number`
  - `errorCount: number`
  - `warningCount: number`
  - `infoCount: number`
- `repairSuggestions: RepairSuggestion[]` - Suggested repairs

#### 8. **Chat** (`chat`)
Manages chat messages and agent status.
- `messages: ChatMessage[]` - Array of chat messages
  - Each message has: `id`, `role` ("user" | "agent" | "system"), `content`, `timestamp`, `agentNode?` (optional)
- `agentStatus: AgentStatus` - Current agent status
  - Values: `"idle" | "running" | "waiting_confirmation"`

## Actions

All actions are typed and return `void`. They update the store state immutably.

### Available Actions

1. **`setProjectStatus(status: ProjectStatus)`**
   - Updates the project status

2. **`setContext(context: Partial<Context>)`**
   - Merges partial context updates

3. **`setSchema(schema: Schema)`**
   - Replaces the entire schema

4. **`setProfile(profile: Profile)`**
   - Replaces the entire profile

5. **`setRules(rules: Rules)`**
   - Replaces the entire rules

6. **`setGenerationStatus(status: GenerationStatus)`**
   - Updates the generation status

7. **`addChatMessage(message: ChatMessage)`**
   - Appends a new chat message

8. **`setAgentStatus(status: AgentStatus)`**
   - Updates the agent status

9. **`addIteration(iteration: GenerationIteration)`**
   - Adds a new iteration and updates currentIteration

10. **`setValidationResults(results: ValidationResult[])`**
    - Replaces validation results

## Type Safety

- **Strict TypeScript**: No `any` types used
- **Union Types**: All status fields use union types for type safety
- **Optional Fields**: Explicitly marked with `?`
- **Immutable Updates**: All state updates use spread operators
- **Initial State**: All slices have sensible default values

## Initial State

All state slices are initialized with empty/default values:
- Empty arrays for collections
- Empty objects for records
- Default union type values (e.g., `"idle"` for status fields)
- Empty strings for text fields
- Zero for numeric fields

## Usage Example

```typescript
import { useAppStore } from '@/store';

// Get state
const projectStatus = useAppStore((state) => state.project.status);
const messages = useAppStore((state) => state.chat.messages);

// Update state
useAppStore.getState().setProjectStatus('generating');
useAppStore.getState().addChatMessage({
  id: '1',
  role: 'user',
  content: 'Generate synthetic data',
  timestamp: new Date().toISOString(),
});
```

## Files Modified

- `frontend/src/types/index.ts` - Complete type definitions
- `frontend/src/store/index.ts` - Zustand store implementation

## Notes

- This is a pure state management layer with no backend integration
- No UI components are connected to this store
- All actions are synchronous and update state immediately
- Store is ready for integration with React components and backend API calls
