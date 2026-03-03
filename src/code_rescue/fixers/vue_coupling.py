"""Vue coupling fixer - generates composable scaffolds and coupling remediation.

Handles rules from VueCouplingAnalyzer:
    VUE-COMPOSE-001:   State group → composable scaffold
    VUE-COMPOSE-002:   Mixed concerns → separation hints
    VUE-COUPLE-001:    Excessive props → restructure suggestions
    VUE-COUPLE-002:    Excessive emits → event consolidation
    VUE-COUPLE-003:    High component coupling → provide/inject
    VUE-COUPLE-004:    Prop drilling → store or provide/inject

This fixer generates NEW files (scaffolds) and refactoring hints rather than
directly modifying existing code, since Vue refactoring requires human judgment.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from code_rescue.fixers.base import AbstractFixer, FixResult, FixStatus
from code_rescue.fixers.vue_utils import (
    to_pascal as _to_pascal,
    extract_component_name as _extract_component_name,
)
from code_rescue.model.rescue_action import RescueAction


# ══════════════════════════════════════════════════════════════════════════════
# Concern → Composable mapping
# ══════════════════════════════════════════════════════════════════════════════

CONCERN_COMPOSABLES: dict[str, dict[str, Any]] = {
    "data_fetching": {
        "name": "useFetch",
        "imports": ["ref", "watch", "onMounted"],
        "state": ["data", "loading", "error"],
        "functions": ["fetch", "refresh", "reset"],
        "template": '''export function useFetch<T>(url: () => string) {
  const data = ref<T | null>(null)
  const loading = ref(false)
  const error = ref<Error | null>(null)

  async function fetch() {
    loading.value = true
    error.value = null
    try {
      const response = await globalThis.fetch(url())
      data.value = await response.json()
    } catch (e) {
      error.value = e instanceof Error ? e : new Error(String(e))
    } finally {
      loading.value = false
    }
  }

  function refresh() {
    return fetch()
  }

  function reset() {
    data.value = null
    error.value = null
  }

  onMounted(fetch)
  watch(url, fetch)

  return { data, loading, error, fetch, refresh, reset }
}''',
    },
    "form_handling": {
        "name": "useForm",
        "imports": ["ref", "computed"],
        "state": ["formData", "errors", "isSubmitting", "isDirty"],
        "functions": ["validate", "submit", "reset", "setField", "setError"],
        "template": '''export function useForm<T extends Record<string, unknown>>(initialData: T) {
  const formData = ref({ ...initialData })
  const errors = ref<Record<string, string>>({})
  const isSubmitting = ref(false)
  const isDirty = computed(() => JSON.stringify(formData.value) !== JSON.stringify(initialData))

  function setField(key: keyof T, value: unknown) {
    ;(formData.value as Record<string, unknown>)[key as string] = value
    delete errors.value[key as string]
  }

  function setError(key: keyof T, message: string) {
    errors.value[key as string] = message
  }

  function validate(): boolean {
    errors.value = {}
    // TODO: Add validation rules
    return Object.keys(errors.value).length === 0
  }

  async function submit(handler: (data: T) => Promise<void>) {
    if (!validate()) return false
    isSubmitting.value = true
    try {
      await handler(formData.value as T)
      return true
    } finally {
      isSubmitting.value = false
    }
  }

  function reset() {
    formData.value = { ...initialData }
    errors.value = {}
  }

  return { formData, errors, isSubmitting, isDirty, setField, setError, validate, submit, reset }
}''',
    },
    "pagination": {
        "name": "usePagination",
        "imports": ["ref", "computed"],
        "state": ["page", "pageSize", "totalItems"],
        "functions": ["nextPage", "prevPage", "goToPage", "setPageSize"],
        "template": '''export function usePagination(options: { pageSize?: number; totalItems?: number } = {}) {
  const page = ref(1)
  const pageSize = ref(options.pageSize ?? 10)
  const totalItems = ref(options.totalItems ?? 0)

  const totalPages = computed(() => Math.ceil(totalItems.value / pageSize.value))
  const hasNextPage = computed(() => page.value < totalPages.value)
  const hasPrevPage = computed(() => page.value > 1)
  const offset = computed(() => (page.value - 1) * pageSize.value)

  function nextPage() {
    if (hasNextPage.value) page.value++
  }

  function prevPage() {
    if (hasPrevPage.value) page.value--
  }

  function goToPage(n: number) {
    page.value = Math.max(1, Math.min(n, totalPages.value))
  }

  function setPageSize(size: number) {
    pageSize.value = size
    page.value = 1
  }

  return {
    page, pageSize, totalItems, totalPages,
    hasNextPage, hasPrevPage, offset,
    nextPage, prevPage, goToPage, setPageSize,
  }
}''',
    },
    "selection": {
        "name": "useSelection",
        "imports": ["ref", "computed"],
        "state": ["selected"],
        "functions": ["toggle", "select", "deselect", "selectAll", "clear", "isSelected"],
        "template": '''export function useSelection<T extends { id: string }>(items: () => T[]) {
  const selected = ref<Set<string>>(new Set())

  const selectedItems = computed(() => items().filter(i => selected.value.has(i.id)))
  const selectedCount = computed(() => selected.value.size)
  const isAllSelected = computed(() => items().length > 0 && selected.value.size === items().length)
  const isPartiallySelected = computed(() => selected.value.size > 0 && !isAllSelected.value)

  function isSelected(id: string): boolean {
    return selected.value.has(id)
  }

  function toggle(id: string) {
    if (selected.value.has(id)) {
      selected.value.delete(id)
    } else {
      selected.value.add(id)
    }
  }

  function select(id: string) {
    selected.value.add(id)
  }

  function deselect(id: string) {
    selected.value.delete(id)
  }

  function selectAll() {
    items().forEach(i => selected.value.add(i.id))
  }

  function clear() {
    selected.value.clear()
  }

  return {
    selected, selectedItems, selectedCount,
    isAllSelected, isPartiallySelected,
    isSelected, toggle, select, deselect, selectAll, clear,
  }
}''',
    },
    "undo_redo": {
        "name": "useUndoRedo",
        "imports": ["ref", "computed"],
        "state": ["history", "index"],
        "functions": ["push", "undo", "redo", "clear", "canUndo", "canRedo"],
        "template": '''export function useUndoRedo<T>(initialState: T) {
  const history = ref<T[]>([initialState])
  const index = ref(0)

  const current = computed(() => history.value[index.value])
  const canUndo = computed(() => index.value > 0)
  const canRedo = computed(() => index.value < history.value.length - 1)

  function push(state: T) {
    // Truncate future history
    history.value = history.value.slice(0, index.value + 1)
    history.value.push(state)
    index.value = history.value.length - 1
  }

  function undo() {
    if (canUndo.value) index.value--
  }

  function redo() {
    if (canRedo.value) index.value++
  }

  function clear() {
    history.value = [current.value]
    index.value = 0
  }

  return { current, history, canUndo, canRedo, push, undo, redo, clear }
}''',
    },
    "modal_state": {
        "name": "useModal",
        "imports": ["ref"],
        "state": ["isOpen", "data"],
        "functions": ["open", "close", "toggle"],
        "template": '''export function useModal<T = unknown>() {
  const isOpen = ref(false)
  const data = ref<T | null>(null)

  function open(payload?: T) {
    data.value = payload ?? null
    isOpen.value = true
  }

  function close() {
    isOpen.value = false
    data.value = null
  }

  function toggle() {
    isOpen.value ? close() : open()
  }

  return { isOpen, data, open, close, toggle }
}''',
    },
}


# ══════════════════════════════════════════════════════════════════════════════
# Fixer class
# ══════════════════════════════════════════════════════════════════════════════


class VueCouplingFixer(AbstractFixer):
    """Fixer for Vue component coupling issues.

    Generates scaffolds and refactoring hints for:
    - State groups → composable extraction (VUE-COMPOSE-001)
    - Mixed concerns → concern separation (VUE-COMPOSE-002)
    - Excessive props → restructuring (VUE-COUPLE-001)
    - Excessive emits → event consolidation (VUE-COUPLE-002)
    - High coupling → provide/inject (VUE-COUPLE-003)
    - Prop drilling → store/provide (VUE-COUPLE-004)
    """

    SUPPORTED_RULES = [
        "VUE-COMPOSE-001",
        "VUE-COMPOSE-002",
        "VUE-COUPLE-001",
        "VUE-COUPLE-002",
        "VUE-COUPLE-003",
        "VUE-COUPLE-004",
    ]

    @property
    def supported_rules(self) -> list[str]:
        return self.SUPPORTED_RULES

    def can_fix(self, action: RescueAction) -> bool:
        return action.rule_id in self.SUPPORTED_RULES

    def generate_fix(
        self,
        action: RescueAction,
        source_code: str,
    ) -> tuple[str | None, str | None]:
        """Generate fix based on rule type."""
        rule_id = action.rule_id

        if rule_id == "VUE-COMPOSE-001":
            return self._generate_state_group_composable(action, source_code)
        elif rule_id == "VUE-COMPOSE-002":
            return self._generate_concern_separation_hints(action, source_code)
        elif rule_id == "VUE-COUPLE-001":
            return self._generate_props_restructure(action, source_code)
        elif rule_id == "VUE-COUPLE-002":
            return self._generate_emits_consolidation(action, source_code)
        elif rule_id == "VUE-COUPLE-003":
            return self._generate_coupling_reduction(action, source_code)
        elif rule_id == "VUE-COUPLE-004":
            return self._generate_prop_drilling_fix(action, source_code)

        return None, None

    def _generate_state_group_composable(
        self,
        action: RescueAction,
        source_code: str,
    ) -> tuple[str | None, str | None]:
        """Generate composable scaffold for state group extraction."""
        metadata = action.metadata
        suggested_name = metadata.get("suggested_composable", "useExtracted")
        refs = metadata.get("refs", [])
        group_concern = metadata.get("group_concern", "")

        # Check if we have a template for this concern
        if group_concern in CONCERN_COMPOSABLES:
            template = CONCERN_COMPOSABLES[group_concern]
            scaffold = f"""import {{ {", ".join(template["imports"])} }} from 'vue'

/**
 * {template["name"]} - Extracted from component
 * Concern: {group_concern}
 *
 * Detected refs: {", ".join(refs) if refs else "none"}
 */

{template["template"]}
"""
            rationale = (
                f"Extract {group_concern} logic to {template['name']}(). "
                f"This is a common pattern with well-known state/function shapes. "
                f"Review the template and customize for your specific needs."
            )
        else:
            # Generate generic composable from refs
            ref_decls = "\n  ".join(
                f"const {r} = ref(null)  // TODO: type and initial value"
                for r in refs
            )
            exports = ", ".join(refs)

            scaffold = f"""import {{ ref, computed }} from 'vue'

/**
 * {suggested_name} - Extracted state group
 * Detected refs: {", ".join(refs)}
 */
export function {suggested_name}() {{
  // === State ===
  {ref_decls if refs else "// No refs detected"}

  // === Functions ===
  // TODO: Move related functions here

  return {{
    {exports if refs else "// TODO: export state and functions"}
  }}
}}
"""
            rationale = (
                f"Extract {len(refs)} related refs to {suggested_name}(). "
                "Move cohesive functions that operate on this state into the composable."
            )

        combined = f"=== NEW FILE: composables/{suggested_name}.ts ===\n{scaffold}"
        return combined, rationale

    def _generate_concern_separation_hints(
        self,
        action: RescueAction,
        source_code: str,
    ) -> tuple[str | None, str | None]:
        """Generate separation hints for mixed concerns."""
        metadata = action.metadata
        concerns = metadata.get("concerns", [])
        component_name = _extract_component_name(action.file_path)

        if not concerns:
            return None, None

        # Generate composable suggestion for each concern
        sections = []
        wiring_imports = []
        wiring_usages = []

        for concern in concerns:
            if concern in CONCERN_COMPOSABLES:
                tmpl = CONCERN_COMPOSABLES[concern]
                name = tmpl["name"]
                wiring_imports.append(f"import {{ {name} }} from '@/composables/{name}'")
                wiring_usages.append(
                    f"const {{ {', '.join(tmpl['state'][:3])}, ... }} = {name}(...)"
                )
                sections.append(
                    f"### {concern} → {name}\n"
                    f"State: {', '.join(tmpl['state'])}\n"
                    f"Functions: {', '.join(tmpl['functions'])}\n"
                )
            else:
                generic_name = f"use{_to_pascal(concern)}"
                wiring_imports.append(
                    f"import {{ {generic_name} }} from '@/composables/{generic_name}'"
                )
                wiring_usages.append(f"const {{ ... }} = {generic_name}()")
                sections.append(
                    f"### {concern} → {generic_name}\n"
                    f"TODO: Define state and functions for this concern.\n"
                )

        hint = f"""# Concern Separation Plan: {component_name}

## Detected Concerns
{chr(10).join(f"- {c}" for c in concerns)}

## Recommended Composables

{chr(10).join(sections)}

## Component Wiring

```typescript
{chr(10).join(wiring_imports)}

// In setup:
{chr(10).join(wiring_usages)}
```

## Separation Steps

1. Create composable files under `composables/`
2. Move concern-specific refs and functions to each composable
3. Import and wire up in component
4. Run type-check after each move
5. Test that behavior is preserved
"""

        rationale = (
            f"Component mixes {len(concerns)} concerns: {', '.join(concerns)}. "
            "Extract each to a dedicated composable for better testability and reuse."
        )

        return hint, rationale

    def _generate_props_restructure(
        self,
        action: RescueAction,
        source_code: str,
    ) -> tuple[str | None, str | None]:
        """Generate restructuring suggestions for excessive props."""
        metadata = action.metadata
        prop_count = metadata.get("prop_count", 0)
        props = metadata.get("props", [])

        # Group props by potential object types
        user_props = [p for p in props if "user" in p.lower() or "author" in p.lower()]
        config_props = [p for p in props if p.endswith("Config") or p.endswith("Options")]
        style_props = [p for p in props if "style" in p.lower() or "class" in p.lower()]
        other_props = [
            p for p in props if p not in user_props + config_props + style_props
        ]

        groups = []
        if user_props:
            groups.append(("user: User", user_props))
        if config_props:
            groups.append(("config: Config", config_props))
        if style_props:
            groups.append(("styleProps: StyleProps", style_props))
        if other_props and len(other_props) > 3:
            groups.append(("data: DataProps", other_props))

        hint = f"""# Props Restructuring Plan

## Current State
- {prop_count} individual props
- Props: {', '.join(props[:10])}{'...' if len(props) > 10 else ''}

## Recommended Grouping

"""
        for group_type, group_props in groups:
            hint += f"""### {group_type}
```typescript
interface {group_type.split(':')[1].strip()} {{
  {chr(10).join(f'  {p}: unknown;  // TODO: type' for p in group_props)}
}}
```

"""

        hint += """## Refactoring Steps

1. Define interface types for prop groups
2. Update parent components to pass grouped objects
3. Update child component to destructure
4. Consider v-bind="$props" for pass-through scenarios

## Alternative: Provide/Inject

If props are passed through multiple levels, consider:

```typescript
// Parent
provide('user', user)

// Child (any depth)
const user = inject<User>('user')
```
"""

        rationale = (
            f"{prop_count} props exceeds recommended maximum (8). "
            f"Group related props into objects or use provide/inject for deep passing."
        )

        return hint, rationale

    def _generate_emits_consolidation(
        self,
        action: RescueAction,
        source_code: str,
    ) -> tuple[str | None, str | None]:
        """Generate consolidation suggestions for excessive emits."""
        metadata = action.metadata
        emit_count = metadata.get("emit_count", 0)
        emits = metadata.get("emits", [])

        # Group emits by verb prefix
        crud_emits = [e for e in emits if e.startswith(("create", "update", "delete", "save"))]
        nav_emits = [e for e in emits if e.startswith(("go", "navigate", "select"))]
        state_emits = [e for e in emits if e.startswith(("open", "close", "toggle", "show", "hide"))]
        other_emits = [e for e in emits if e not in crud_emits + nav_emits + state_emits]

        hint = f"""# Event Consolidation Plan

## Current State
- {emit_count} individual emit events
- Events: {', '.join(emits[:10])}{'...' if len(emits) > 10 else ''}

## Recommended Consolidation

### Option A: Action Pattern
Consolidate CRUD/action events into a single action event:

```typescript
// Before
emit('create', payload)
emit('update', payload)
emit('delete', payload)

// After
emit('action', {{ type: 'create', payload }})
emit('action', {{ type: 'update', payload }})
emit('action', {{ type: 'delete', payload }})
```

### Option B: v-model Pattern
For state emits, use v-model:

```typescript
// Before
emit('open')
emit('close')
emit('toggle')

// After
emit('update:isOpen', true)
emit('update:isOpen', false)
emit('update:isOpen', !props.isOpen)
```

### Option C: Callback Props
For complex interactions, pass handler functions as props:

```typescript
// Parent
<MyComponent :onSave="handleSave" :onCancel="handleCancel" />

// Child (no emit needed)
props.onSave?.(data)
```

## Grouping Analysis

- CRUD events ({len(crud_emits)}): {', '.join(crud_emits) or 'none'}
- Navigation events ({len(nav_emits)}): {', '.join(nav_emits) or 'none'}
- State events ({len(state_emits)}): {', '.join(state_emits) or 'none'}
- Other ({len(other_emits)}): {', '.join(other_emits) or 'none'}
"""

        rationale = (
            f"{emit_count} emits exceeds recommended maximum (6). "
            f"Consolidate related events using action pattern or v-model."
        )

        return hint, rationale

    def _generate_coupling_reduction(
        self,
        action: RescueAction,
        source_code: str,
    ) -> tuple[str | None, str | None]:
        """Generate coupling reduction suggestions for high component imports."""
        metadata = action.metadata
        import_count = metadata.get("import_count", 0)
        imports = metadata.get("component_imports", [])

        hint = f"""# Coupling Reduction Plan

## Current State
- {import_count} direct component imports
- Components: {', '.join(imports[:10])}{'...' if len(imports) > 10 else ''}

## Strategies

### 1. Slots Instead of Imports
Replace some child components with slots for flexibility:

```vue
<!-- Before: tightly coupled -->
<template>
  <div>
    <HeaderPanel />
    <SidebarPanel />
    <ContentPanel />
  </div>
</template>

<!-- After: slot-based -->
<template>
  <div>
    <slot name="header" />
    <slot name="sidebar" />
    <slot name="content" />
  </div>
</template>
```

### 2. Dynamic Components
For switchable content, use dynamic components:

```vue
<component :is="currentPanel" v-bind="panelProps" />
```

### 3. Provide/Inject for Services
For shared services/utilities, use provide/inject:

```typescript
// Layout.vue
provide('layoutService', {{
  toggleSidebar: () => {{ ... }},
  setTitle: (t: string) => {{ ... }},
}})

// Any child (no import needed)
const layout = inject('layoutService')
```

### 4. Composition via Composables
Extract shared logic to composables that multiple components import:

```typescript
// Instead of importing 7 UI components that all need the same state,
// have them all use a shared composable
const {{ data, loading }} = useDashboardData()
```

## Recommended Imports to Extract

Based on naming patterns:
- Panel components → consider slots
- Service/utility components → consider provide/inject
- Data-sharing components → consider composables
"""

        rationale = (
            f"{import_count} component imports indicates high coupling. "
            f"Consider slots, dynamic components, or provide/inject."
        )

        return hint, rationale

    def _generate_prop_drilling_fix(
        self,
        action: RescueAction,
        source_code: str,
    ) -> tuple[str | None, str | None]:
        """Generate fix suggestions for prop drilling."""
        metadata = action.metadata
        drilled_props = metadata.get("drilled_props", [])
        used_props = metadata.get("used_props", [])
        depth_estimate = metadata.get("depth_estimate", "unknown")

        hint = f"""# Prop Drilling Remediation

## Current State
- Drilled props (passed through): {', '.join(drilled_props) if drilled_props else 'unknown'}
- Used locally: {', '.join(used_props) if used_props else 'unknown'}
- Estimated drilling depth: {depth_estimate}

## Solution: Provide/Inject

### Step 1: Identify Drilling Root
Find the highest ancestor that owns the drilled state.

### Step 2: Provide at Root

```typescript
// In the ancestor component that owns the state
import {{ provide, ref }} from 'vue'

const user = ref({{ id: '...', name: '...', role: '...' }})
provide('user', user)
provide('theme', props.theme)
provide('locale', props.locale)
```

### Step 3: Inject in Consumers

```typescript
// In any descendant (no prop drilling needed)
import {{ inject }} from 'vue'

const user = inject<Ref<User>>('user')
const theme = inject<string>('theme', 'light')  // with default
```

### Step 4: Remove Intermediate Props
Delete the pass-through props from intermediate components.

## Alternative: Pinia Store

For app-wide state, consider a Pinia store:

```typescript
// stores/user.ts
export const useUserStore = defineStore('user', {{
  state: () => ({{ user: null as User | null }}),
  actions: {{
    setUser(u: User) {{ this.user = u }}
  }}
}})

// Any component
const userStore = useUserStore()
// userStore.user
```

## Type Safety

Create injection keys for type safety:

```typescript
// injection-keys.ts
import type {{ InjectionKey, Ref }} from 'vue'
import type {{ User }} from './types'

export const UserKey: InjectionKey<Ref<User>> = Symbol('user')
export const ThemeKey: InjectionKey<string> = Symbol('theme')
```
"""

        rationale = (
            f"Prop drilling detected: {len(drilled_props)} props passed through without local use. "
            f"Use provide/inject or Pinia store to avoid intermediary prop passing."
        )

        return hint, rationale

    def apply(
        self,
        action: RescueAction,
        source_code: str,
        dry_run: bool = True,
    ) -> FixResult:
        """Apply Vue coupling fix (generates hints, doesn't modify source)."""
        if not self.can_fix(action):
            return FixResult(
                status=FixStatus.SKIPPED,
                action=action,
                message=f"Fixer does not support rule: {action.rule_id}",
            )

        hint, rationale = self.generate_fix(action, source_code)
        if hint is None:
            return FixResult(
                status=FixStatus.FAILED,
                action=action,
                message="Could not generate remediation hint",
            )

        action.replacement_code = hint
        if rationale:
            action.rationale = rationale

        # Note: Coupling fixes are hints/scaffolds, not direct modifications
        return FixResult(
            status=FixStatus.SUCCESS,
            action=action,
            original_content=source_code,
            modified_content=None,  # Source not modified
            message="Remediation scaffold generated (review and apply manually)",
        )


# ══════════════════════════════════════════════════════════════════════════════
# Standalone utilities for CLI usage
# ══════════════════════════════════════════════════════════════════════════════


def generate_composable_from_concern(concern: str) -> str | None:
    """Generate a composable scaffold for a known concern.

    Args:
        concern: One of the known concern types (data_fetching, form_handling, etc.)

    Returns:
        Composable TypeScript code or None if concern not recognized
    """
    if concern not in CONCERN_COMPOSABLES:
        return None

    tmpl = CONCERN_COMPOSABLES[concern]
    return f"""import {{ {", ".join(tmpl["imports"])} }} from 'vue'

{tmpl["template"]}
"""


def list_known_concerns() -> list[str]:
    """Return list of concerns with known composable patterns."""
    return list(CONCERN_COMPOSABLES.keys())
