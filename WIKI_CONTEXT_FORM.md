# Context Form Component

**Commit**: `b956d2d` - Add ContextForm component with 9 form fields connected to Zustand store

## Overview

Context form component for the left panel in Studio.tsx. Collects user input for project context, requirements, and constraints. All form fields are connected to the Zustand store with live updates (no submit button).

## Architecture

### Form Fields (9 total)

| # | Field | Type | Store Key | Behavior |
|---|-------|------|-----------|----------|
| 1 | Primary objective | textarea | context.objective | Live update to store |
| 2 | Downstream use | select | context.useCase | Options: ml_training, analytics, qa_testing, regulatory |
| 3 | Data dictionary upload | file input | Local state | Accept: .txt, .sql, .csv |
| 4 | Sample data upload | file input | Local state | Accept: .csv |
| 5 | Tables in scope | text input | Local state | Comma-separated string |
| 6 | Output size (rows) | number input | context.targetRowCounts | Min: 100, Max: 10,000,000 |
| 7 | Privacy requirement | select | context.privacyLevel | Options: none, no_verbatim_pii, k5, k10 |
| 8 | Scenario description | textarea | context.scenarioDescription | Live update to store |
| 9 | Additional constraints | textarea | context.additionalConstraints | Live update to store |

### State Management

**Zustand Store Fields:**
- `context.objective` - Primary objective text
- `context.useCase` - Downstream use case (union type)
- `context.privacyLevel` - Privacy level requirement (union type)
- `context.targetRowCounts` - Target row counts as { _default: number }
- `context.scenarioDescription` - Scenario description text
- `context.additionalConstraints` - Additional constraints text

**Local State (not in store):**
- `dataDictFile: string | null` - Data dictionary filename
- `sampleDataFile: string | null` - Sample data filename
- `tablesInScope: string` - Comma-separated table names

### Form Behavior

- **Live updates**: All store-connected fields call `setContext()` on change
- **No submit button**: Changes flow immediately to store
- **File inputs**: Use `e.target.files?.[0]?.name ?? null` to extract filename
- **Number validation**: Parse with `parseInt()`, guard against `isNaN` before store update
- **Scrollable**: Parent container has `overflow-y-auto` for form overflow

## Component Details

### ContextForm.tsx

```typescript
export function ContextForm(): JSX.Element
```

**Key Features:**
- Strict TypeScript (no `any` types)
- Local state for file uploads and table names
- Zustand store integration for context fields
- Type-safe select options (UseCase, PrivacyLevel)
- Tailwind CSS styling with focus rings and borders
- Form field labels with descriptive text
- Placeholder text for guidance

### Handler Functions

- `handleObjectiveChange()` - Update objective in store
- `handleUseCaseChange()` - Update useCase in store (cast to UseCase)
- `handleDataDictUpload()` - Store filename in local state
- `handleSampleDataUpload()` - Store filename in local state
- `handleTablesInScopeChange()` - Update local state
- `handleOutputSizeChange()` - Parse and validate number, update store
- `handlePrivacyLevelChange()` - Update privacyLevel in store (cast to PrivacyLevel)
- `handleScenarioChange()` - Update scenarioDescription in store
- `handleConstraintsChange()` - Update additionalConstraints in store

## Styling

- **Tailwind CSS only**: No inline styles, no CSS files
- **Form layout**: Vertical stack with `space-y-4` between fields
- **Input styling**: Border, rounded corners, focus ring (blue-500)
- **Labels**: Small font, medium weight, gray-700 color
- **File feedback**: Small gray text showing uploaded filename

## Integration

### Studio.tsx Update

Replaced placeholder div with `<ContextForm />` component:

```typescript
// Before
<div className="text-gray-600">Context Form — Phase 3</div>

// After
<ContextForm />
```

## Build Status

✅ TypeScript build passes with zero errors

## Files

### Created
- `frontend/src/components/forms/ContextForm.tsx` - 200+ lines

### Modified
- `frontend/src/pages/Studio.tsx` - Import and use ContextForm

## Future Enhancements

- Phase 3 completion: File upload backend integration
- Table parsing from comma-separated input
- Form validation and error messages
- Preset templates for common scenarios
- Form reset functionality

## Notes

- File uploads are stored locally; backend integration pending
- Table names are not parsed; stored as raw comma-separated string
- Output size stored as `{ _default: value }` for future multi-table support
- No form submission; all changes are live updates to store
- Ready for integration with backend file upload endpoints in future phases
