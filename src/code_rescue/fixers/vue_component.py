"""Vue component fixer - generates extraction scaffolds for god objects.

Handles:
    VUE-GOD-001/002/003: Generate decomposition plan
    VUE-EXTRACT-001:     Generate child component scaffold
    VUE-COMPOSABLE-001:  Generate composable scaffold

This fixer generates NEW files (scaffolds) rather than modifying existing ones,
since Vue decomposition requires human judgment for prop/event wiring.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from code_rescue.fixers.base import AbstractFixer, FixResult, FixStatus
from code_rescue.fixers.vue_utils import to_pascal as _to_pascal, to_kebab as _to_kebab
from code_rescue.model.rescue_action import RescueAction


@dataclass(slots=True)
class ExtractionPlan:
    """Plan for extracting a section from a Vue component."""

    source_file: str
    target_file: str
    section_name: str
    line_start: int
    line_end: int
    scaffold: str
    parent_wiring: str
    rationale: str


class VueComponentFixer(AbstractFixer):
    """Fixer for Vue component god objects.

    Generates extraction scaffolds for:
    - Template sections (VUE-EXTRACT-001) → Child component .vue files
    - Script logic (VUE-COMPOSABLE-001) → Composable .ts files
    - God objects (VUE-GOD-*) → Decomposition plan
    """

    SUPPORTED_RULES = [
        "VUE-GOD-001",
        "VUE-GOD-002",
        "VUE-GOD-003",
        "VUE-EXTRACT-001",
        "VUE-COMPOSABLE-001",
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

        if rule_id == "VUE-EXTRACT-001":
            return self._generate_component_extraction(action, source_code)
        elif rule_id == "VUE-COMPOSABLE-001":
            return self._generate_composable_extraction(action, source_code)
        elif rule_id.startswith("VUE-GOD-"):
            return self._generate_decomposition_plan(action, source_code)

        return None, None

    def _generate_component_extraction(
        self,
        action: RescueAction,
        source_code: str,
    ) -> tuple[str | None, str | None]:
        """Generate a child component scaffold from template section."""
        metadata = action.metadata
        section_name = metadata.get("section_name", "Section")
        component_name = metadata.get("suggested_component_name", "ExtractedPanel")
        line_count = metadata.get("line_count", 0)

        # Extract the template section
        lines = source_code.splitlines()
        line_start = action.line_start - 1
        line_end = action.line_end

        if line_start < 0 or line_end > len(lines):
            return None, None

        template_lines = lines[line_start:line_end]
        template_content = "\n".join(template_lines)

        # Detect reactive data bindings used in this section
        v_models = set(re.findall(r'v-model(?::\w+)?="(\w+)"', template_content))
        v_binds = set(re.findall(r':(\w+)="(\w+)"', template_content))
        emits = set(re.findall(r'@(\w+)="(\w+)"', template_content))

        # Build props and emits from detected bindings
        props = list(v_models | {b[1] for b in v_binds})
        emit_events = list({e[0] for e in emits})

        # Generate scaffold
        scaffold = _generate_vue_component_scaffold(
            component_name=component_name,
            section_name=section_name,
            template_content=template_content,
            props=props,
            emits=emit_events,
        )

        # Generate parent wiring snippet
        props_str = " ".join(f':{p}="{p}"' for p in props)
        emits_str = " ".join(f'@{e}="handle{_to_pascal(e)}"' for e in emit_events)
        parent_wiring = f"""
<!-- Replace {line_count} lines with: -->
<{component_name}
  {props_str}
  {emits_str}
/>

<!-- Import: -->
import {component_name} from '@/components/{_to_kebab(component_name)}/{component_name}.vue'
"""

        rationale = (
            f"Extract '{section_name}' ({line_count} lines) to <{component_name}/>. "
            f"Detected bindings: {len(props)} props, {len(emit_events)} events. "
            "Review prop types and add explicit TypeScript interfaces."
        )

        # Return scaffold as replacement_code, parent wiring in rationale
        combined = f"=== NEW FILE: {component_name}.vue ===\n{scaffold}\n\n=== PARENT WIRING ===\n{parent_wiring}"
        return combined, rationale

    def _generate_composable_extraction(
        self,
        action: RescueAction,
        source_code: str,
    ) -> tuple[str | None, str | None]:
        """Generate a composable scaffold from script-heavy component."""
        metadata = action.metadata
        component_name = metadata.get("component_name", "Component")
        script_lines = metadata.get("script_lines", 0)
        suggested_name = metadata.get("suggested_composable", f"use{component_name}")

        # Parse script section to extract reactive state and functions
        script_match = re.search(
            r"<script[^>]*>(.*?)</script>",
            source_code,
            re.DOTALL,
        )
        if not script_match:
            return None, None

        script_content = script_match.group(1)

        # Detect refs, computed, functions
        refs = re.findall(r"const\s+(\w+)\s*=\s*ref\(", script_content)
        reactives = re.findall(r"const\s+(\w+)\s*=\s*reactive\(", script_content)
        computeds = re.findall(r"const\s+(\w+)\s*=\s*computed\(", script_content)
        functions = re.findall(r"(?:const|function)\s+(\w+)\s*=?\s*(?:async\s*)?\(", script_content)

        # Filter out lifecycle hooks and built-ins
        excluded = {"onMounted", "onUnmounted", "watch", "watchEffect", "ref", "computed", "reactive"}
        functions = [f for f in functions if f not in excluded and not f.startswith("_")]

        # Generate composable scaffold
        scaffold = _generate_composable_scaffold(
            composable_name=suggested_name,
            refs=refs,
            reactives=reactives,
            computeds=computeds,
            functions=functions[:10],  # Limit to avoid giant exports
        )

        # Generate component wiring
        exports = refs + reactives + computeds + functions[:10]
        wiring = f"""
<!-- In component script: -->
const {{ {", ".join(exports[:8])}{"..." if len(exports) > 8 else ""} }} = {suggested_name}()
"""

        rationale = (
            f"Extract {script_lines} lines of script logic to {suggested_name}(). "
            f"Detected: {len(refs)} refs, {len(computeds)} computed, {len(functions)} functions. "
            "Review dependencies and move only cohesive state/logic."
        )

        combined = f"=== NEW FILE: {suggested_name}.ts ===\n{scaffold}\n\n=== COMPONENT WIRING ===\n{wiring}"
        return combined, rationale

    def _generate_decomposition_plan(
        self,
        action: RescueAction,
        source_code: str,
    ) -> tuple[str | None, str | None]:
        """Generate decomposition plan for god object component."""
        metadata = action.metadata
        component_name = metadata.get("component_name", "Component")
        total_lines = metadata.get("total_lines", 0)
        template_lines = metadata.get("template_lines", 0)
        script_lines = metadata.get("script_lines", 0)
        template_ratio = metadata.get("template_ratio", 0)
        script_ratio = metadata.get("script_ratio", 0)

        # Determine strategy based on ratios
        strategies = []

        if template_ratio > 0.6:
            strategies.append(
                "- **Template-heavy**: Identify extractable sections with <!-- Comment --> markers. "
                "Create child components for each logical section (e.g., HeaderPanel, FilterBar, ResultsTable)."
            )
        if script_ratio > 0.6:
            strategies.append(
                f"- **Script-heavy**: Extract to composable use{component_name}(). "
                "Group cohesive state and functions together."
            )
        if not strategies:
            strategies.append(
                "- **Balanced**: Look for natural boundaries between features. "
                "Extract both child components (template) and composables (logic)."
            )

        # Suggest target sizes
        target_components = max(2, total_lines // 400)
        target_loc_each = total_lines // target_components

        plan = f"""# Decomposition Plan: {component_name}.vue

## Current State
- Total: {total_lines} LOC (template: {template_lines}, script: {script_lines})
- Template ratio: {template_ratio:.0%} | Script ratio: {script_ratio:.0%}

## Strategy
{chr(10).join(strategies)}

## Target
- Split into ~{target_components} components of ~{target_loc_each} LOC each
- Main component should be <500 LOC after extraction

## Suggested Extraction Order
1. Extract UI patterns first (cards, panels, forms)
2. Extract shared state to composables
3. Wire props/events between parent and children
4. Run type-check after each extraction

## Pattern Reference
```vue
<!-- Before: inline section -->
<div class="section">
  <h3>Title</h3>
  <input v-model="value" />
  <button @click="doThing">Action</button>
</div>

<!-- After: child component -->
<SectionPanel
  :value="value"
  @update:value="value = $event"
  @action="doThing"
/>
```
"""

        rationale = (
            f"{component_name} is {total_lines} LOC — recommend splitting into "
            f"~{target_components} components. Follow the decomposition plan."
        )

        return plan, rationale

    def apply(
        self,
        action: RescueAction,
        source_code: str,
        dry_run: bool = True,
    ) -> FixResult:
        """Apply Vue component fix (generates scaffold, doesn't modify source)."""
        if not self.can_fix(action):
            return FixResult(
                status=FixStatus.SKIPPED,
                action=action,
                message=f"Fixer does not support rule: {action.rule_id}",
            )

        scaffold, rationale = self.generate_fix(action, source_code)
        if scaffold is None:
            return FixResult(
                status=FixStatus.FAILED,
                action=action,
                message="Could not generate extraction scaffold",
            )

        action.replacement_code = scaffold
        if rationale:
            action.rationale = rationale

        # Note: Vue extraction generates NEW files, doesn't modify source
        return FixResult(
            status=FixStatus.SUCCESS,
            action=action,
            original_content=source_code,
            modified_content=None,  # Source not modified
            message="Extraction scaffold generated (review and apply manually)",
        )


def _generate_vue_component_scaffold(
    component_name: str,
    section_name: str,
    template_content: str,
    props: list[str],
    emits: list[str],
) -> str:
    """Generate a Vue 3 SFC scaffold for extracted component."""
    # Build props interface
    props_interface = "\n  ".join(f"{p}?: unknown;  // TODO: add type" for p in props)
    if not props_interface:
        props_interface = "// No props detected"

    # Build emits interface
    emits_interface = "\n  ".join(f"(e: '{e}', payload?: unknown): void;" for e in emits)
    if not emits_interface:
        emits_interface = "// No emits detected"

    # Indent template content
    indented_template = "\n".join(f"  {line}" for line in template_content.splitlines())

    return f'''<script setup lang="ts">
/**
 * {component_name} - Extracted from parent component
 * Section: {section_name}
 *
 * TODO: Review and refine prop/emit types
 */

interface Props {{
  {props_interface}
}}

interface Emits {{
  {emits_interface}
}}

const props = defineProps<Props>()
const emit = defineEmits<Emits>()
</script>

<template>
{indented_template}
</template>

<style scoped>
/* TODO: Move relevant styles from parent */
</style>
'''


def _generate_composable_scaffold(
    composable_name: str,
    refs: list[str],
    reactives: list[str],
    computeds: list[str],
    functions: list[str],
) -> str:
    """Generate a composable scaffold for extracted logic."""
    # Build ref declarations
    ref_decls = "\n  ".join(f"const {r} = ref(null)  // TODO: add initial value" for r in refs)
    reactive_decls = "\n  ".join(f"const {r} = reactive({{}})  // TODO: add shape" for r in reactives)
    computed_decls = "\n  ".join(f"const {c} = computed(() => null)  // TODO: implement" for c in computeds)
    function_decls = "\n  ".join(f"function {f}() {{\n    // TODO: implement\n  }}" for f in functions)

    # Build exports
    all_exports = refs + reactives + computeds + functions
    exports_str = ",\n    ".join(all_exports) if all_exports else "// No exports detected"

    return f'''import {{ ref, reactive, computed }} from 'vue'

/**
 * {composable_name} - Extracted from component
 *
 * TODO: Review state dependencies and function implementations
 */
export function {composable_name}() {{
  // === State ===
  {ref_decls if refs else "// No refs detected"}
  {reactive_decls if reactives else "// No reactives detected"}

  // === Computed ===
  {computed_decls if computeds else "// No computed detected"}

  // === Functions ===
  {function_decls if functions else "// No functions detected"}

  return {{
    {exports_str}
  }}
}}
'''


# Standalone extraction utilities for CLI usage


def generate_extraction_plan(
    vue_file: Path,
    findings: list[dict[str, Any]],
) -> list[ExtractionPlan]:
    """Generate extraction plans from analyzer findings.

    Args:
        vue_file: Path to the Vue component
        findings: List of finding dicts from VueComponentAnalyzer

    Returns:
        List of ExtractionPlan objects
    """
    plans = []
    source = vue_file.read_text(encoding="utf-8", errors="replace")
    fixer = VueComponentFixer()

    for finding in findings:
        rule_id = finding.get("metadata", {}).get("rule_id", "")
        if rule_id not in fixer.supported_rules:
            continue

        # Build RescueAction from finding
        from code_rescue.model.rescue_action import ActionType, RescueAction, SafetyLevel

        action = RescueAction(
            action_id=finding.get("finding_id", ""),
            finding_id=finding.get("finding_id", ""),
            rule_id=rule_id,
            action_type=ActionType.EXTRACT,
            safety_level=SafetyLevel.MANUAL,
            description=finding.get("message", ""),
            file_path=str(vue_file),
            line_start=finding.get("location", {}).get("line_start", 1),
            line_end=finding.get("location", {}).get("line_end", 1),
            metadata=finding.get("metadata", {}),
        )

        scaffold, rationale = fixer.generate_fix(action, source)
        if scaffold:
            target_name = action.metadata.get("suggested_component_name", "Extracted")
            plans.append(
                ExtractionPlan(
                    source_file=str(vue_file),
                    target_file=f"{target_name}.vue",
                    section_name=action.metadata.get("section_name", "section"),
                    line_start=action.line_start,
                    line_end=action.line_end,
                    scaffold=scaffold,
                    parent_wiring=rationale or "",
                    rationale=rationale or "",
                )
            )

    return plans
