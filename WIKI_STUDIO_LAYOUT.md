# Studio Shell Layout

**Commit**: `468e9e8` - Add Studio shell layout with 7-tab interface

## Overview

Main application page with a 7-tab shell layout. This is a pure UI skeleton with placeholder content for all tabs. No backend integration or store wiring beyond rendering.

## Architecture

### Layout Structure

Full viewport layout (h-screen, overflow-hidden) with two main panels:

```
┌─────────────────────────────────────────────────────┐
│  Left Panel (320px)  │  Main Panel (flex-1)         │
├──────────────────────┼──────────────────────────────┤
│ App Title            │ Tab Bar (7 tabs)             │
│ Context Form         │ ┌────────────────────────────┤
│ Chat Terminal        │ │ Tab Content (active)       │
│                      │ │                            │
│                      │ │                            │
└──────────────────────┴────────────────────────────────┘
```

### Left Panel (Fixed 320px)

Three sections stacked vertically:

1. **App Title / Logo** (fixed height)
   - Static text: "synth-data-studio"
   - Bordered bottom

2. **Context Form Area** (flex-1)
   - Placeholder: "Context Form — Phase 3"
   - Scrollable if content exceeds space
   - Bordered bottom

3. **Chat Terminal Area** (flex-1)
   - Placeholder: "Chat Terminal — Phase 5"
   - Scrollable if content exceeds space

### Main Panel (Flex-1)

Two sections:

1. **Tab Bar** (fixed height)
   - Horizontal button layout
   - 7 tabs with active state styling
   - Blue underline for active tab
   - Hover effects for inactive tabs

2. **Tab Content Area** (flex-1)
   - Renders active tab content
   - Scrollable if content exceeds space

## Tabs

7 tabs in order with phase information:

| Tab | Phase | Purpose |
|-----|-------|---------|
| Chat | 5 | Chat interface with agent |
| Schema | 6 | Database schema definition |
| Profile | 10 | Data profile and statistics |
| Rules | 7 | Business rules and constraints |
| Output | 8 | Generated data output |
| Validation | 9 | Validation results |
| Logs | 11 | System logs and debugging |

## State Management

- **Local useState**: `activeTab` state for tab switching
- **No Zustand integration**: Tab state is local to Studio component
- **No backend calls**: All content is placeholder text

## Styling

- **Tailwind CSS only**: No inline styles, no CSS files
- **Color scheme**:
  - Background: white/gray-50
  - Borders: gray-200
  - Active tab: blue-500/blue-600
  - Text: gray-600/gray-900
- **Responsive**: Flex-based layout adapts to viewport

## Files

### Created
- `frontend/src/pages/Studio.tsx` - Main Studio component (75 lines)

### Modified
- `frontend/src/App.tsx` - Route / to Studio component

## Component Details

### Studio.tsx

```typescript
type TabName = 'Chat' | 'Schema' | 'Profile' | 'Rules' | 'Output' | 'Validation' | 'Logs'

interface TabConfig {
  name: TabName
  phase: number
}

export function Studio(): JSX.Element
```

**Key Features:**
- Strict TypeScript (no `any` types)
- Local state for activeTab
- Tab configuration array with phase numbers
- renderTabContent() helper for dynamic content
- Full viewport layout with overflow-hidden

## Build Status

✅ TypeScript build passes with zero errors
- 35 modules transformed
- Production bundle: 160.14 kB (52.15 kB gzipped)

## Next Steps

Each tab will be implemented in subsequent phases:
- Phase 3: Context Form (left panel)
- Phase 5: Chat Terminal (left panel) + Chat Tab
- Phase 6: Schema Tab
- Phase 7: Rules Tab
- Phase 8: Output Tab
- Phase 9: Validation Tab
- Phase 10: Profile Tab
- Phase 11: Logs Tab

## Notes

- Layout fills entire viewport without overflow
- Left panel is fixed width (320px) for consistent navigation
- Main panel content area is scrollable
- Tab switching is instant (no async operations)
- Ready for integration with Zustand store and backend APIs in future phases
