"""Tests for VueComponentFixer."""

import pytest

from code_rescue.fixers.vue_component import (
    VueComponentFixer,
    ExtractionPlan,
    _generate_vue_component_scaffold,
    _generate_composable_scaffold,
    _to_pascal,
    _to_kebab,
)
from code_rescue.fixers.base import FixStatus
from code_rescue.model.rescue_action import RescueAction, ActionType, SafetyLevel


# Sample Vue components for testing
LARGE_COMPONENT = """<script setup lang="ts">
import { ref, computed } from 'vue'

const items = ref<string[]>([])
const selected = ref<string | null>(null)

const filteredItems = computed(() => {
  return items.value.filter(i => i.includes('test'))
})

function handleClick() {
  console.log('clicked')
}
</script>

<template>
  <div class="container">
    <!-- M.1: Filter Section -->
    <div class="filters">
      <input v-model="searchQuery" placeholder="Search..." />
      <select v-model="category">
        <option value="">All</option>
        <option value="a">Category A</option>
      </select>
""" + "      <span>Filter line</span>\n" * 35 + """
    </div>
    <!-- M.2: Results Section -->
    <div class="results">
      <ul>
        <li v-for="item in filteredItems" :key="item.id">
          {{ item.name }}
        </li>
      </ul>
""" + "      <p>Result line</p>\n" * 50 + """
    </div>
  </div>
</template>

<style scoped>
.container { padding: 1rem; }
</style>
"""


class TestVueComponentFixer:
    """Tests for VueComponentFixer class."""

    def test_supported_rules(self):
        """Fixer supports Vue rules."""
        fixer = VueComponentFixer()
        rules = fixer.supported_rules

        assert "VUE-GOD-001" in rules
        assert "VUE-GOD-002" in rules
        assert "VUE-GOD-003" in rules
        assert "VUE-EXTRACT-001" in rules
        assert "VUE-COMPOSABLE-001" in rules

    def test_can_fix_supported_rule(self):
        """can_fix returns True for supported rules."""
        fixer = VueComponentFixer()
        action = RescueAction(
            action_id="test-1",
            finding_id="finding-1",
            rule_id="VUE-GOD-001",
            file_path="Component.vue",
            line_start=1,
            line_end=100,
            action_type=ActionType.REFACTOR,
            safety_level=SafetyLevel.MANUAL,
            description="God object detected",
        )
        assert fixer.can_fix(action) is True

    def test_cannot_fix_unsupported_rule(self):
        """can_fix returns False for unsupported rules."""
        fixer = VueComponentFixer()
        action = RescueAction(
            action_id="test-1",
            finding_id="finding-1",
            rule_id="SOME_OTHER_RULE",
            file_path="test.py",
            line_start=1,
            line_end=10,
            action_type=ActionType.REPLACE,
            safety_level=SafetyLevel.SAFE,
            description="Other fix",
        )
        assert fixer.can_fix(action) is False

    def test_generate_fix_for_extract(self):
        """generate_fix creates component scaffold for VUE-EXTRACT-001."""
        fixer = VueComponentFixer()
        action = RescueAction(
            action_id="test-1",
            finding_id="finding-1",
            rule_id="VUE-EXTRACT-001",
            file_path="Large.vue",
            line_start=20,
            line_end=60,
            action_type=ActionType.EXTRACT,
            safety_level=SafetyLevel.MANUAL,
            description="Extract section",
            metadata={
                "section_name": "Filter Section",
                "suggested_component_name": "FilterPanel",
                "line_count": 40,
            },
        )

        scaffold, rationale = fixer.generate_fix(action, LARGE_COMPONENT)

        assert scaffold is not None
        assert "FilterPanel.vue" in scaffold
        assert "<script setup lang=\"ts\">" in scaffold
        assert "defineProps" in scaffold
        assert "defineEmits" in scaffold
        assert rationale is not None
        assert "FilterPanel" in rationale

    def test_generate_fix_for_composable(self):
        """generate_fix creates composable scaffold for VUE-COMPOSABLE-001."""
        fixer = VueComponentFixer()
        action = RescueAction(
            action_id="test-1",
            finding_id="finding-1",
            rule_id="VUE-COMPOSABLE-001",
            file_path="Large.vue",
            line_start=1,
            line_end=100,
            action_type=ActionType.EXTRACT,
            safety_level=SafetyLevel.MANUAL,
            description="Extract to composable",
            metadata={
                "component_name": "DataTable",
                "script_lines": 500,
                "script_ratio": 0.85,
                "suggested_composable": "useDataTable",
            },
        )

        scaffold, rationale = fixer.generate_fix(action, LARGE_COMPONENT)

        assert scaffold is not None
        assert "useDataTable.ts" in scaffold
        assert "export function useDataTable" in scaffold
        assert rationale is not None

    def test_generate_fix_for_god_object(self):
        """generate_fix creates decomposition plan for VUE-GOD-* rules."""
        fixer = VueComponentFixer()
        action = RescueAction(
            action_id="test-1",
            finding_id="finding-1",
            rule_id="VUE-GOD-002",
            file_path="Huge.vue",
            line_start=1,
            line_end=900,
            action_type=ActionType.REFACTOR,
            safety_level=SafetyLevel.MANUAL,
            description="God object detected",
            metadata={
                "component_name": "HugeComponent",
                "total_lines": 900,
                "template_lines": 600,
                "script_lines": 200,
                "template_ratio": 0.75,
                "script_ratio": 0.25,
            },
        )

        plan, rationale = fixer.generate_fix(action, LARGE_COMPONENT)

        assert plan is not None
        assert "Decomposition Plan" in plan
        assert "HugeComponent" in plan
        assert "900" in plan  # Total lines
        assert rationale is not None

    def test_apply_generates_scaffold(self):
        """apply returns SUCCESS with scaffold."""
        fixer = VueComponentFixer()
        action = RescueAction(
            action_id="test-1",
            finding_id="finding-1",
            rule_id="VUE-EXTRACT-001",
            file_path="Component.vue",
            line_start=10,
            line_end=50,
            action_type=ActionType.EXTRACT,
            safety_level=SafetyLevel.MANUAL,
            description="Extract section",
            metadata={
                "section_name": "Header",
                "suggested_component_name": "HeaderPanel",
                "line_count": 40,
            },
        )

        result = fixer.apply(action, LARGE_COMPONENT, dry_run=True)

        assert result.status == FixStatus.SUCCESS
        assert result.action.replacement_code is not None
        assert "HeaderPanel" in result.action.replacement_code

    def test_apply_skips_unsupported_rule(self):
        """apply returns SKIPPED for unsupported rules."""
        fixer = VueComponentFixer()
        action = RescueAction(
            action_id="test-1",
            finding_id="finding-1",
            rule_id="UNSUPPORTED_RULE",
            file_path="test.py",
            line_start=1,
            line_end=1,
            action_type=ActionType.REPLACE,
            safety_level=SafetyLevel.SAFE,
            description="Other fix",
        )

        result = fixer.apply(action, "content", dry_run=True)

        assert result.status == FixStatus.SKIPPED


class TestGenerateVueComponentScaffold:
    """Tests for _generate_vue_component_scaffold helper."""

    def test_generates_valid_sfc(self):
        """Generate valid Vue SFC structure."""
        scaffold = _generate_vue_component_scaffold(
            component_name="FilterBar",
            section_name="Filter Section",
            template_content="<div>Content</div>",
            props=["value", "disabled"],
            emits=["update", "submit"],
        )

        assert "<script setup lang=\"ts\">" in scaffold
        assert "FilterBar" in scaffold
        assert "interface Props" in scaffold
        assert "interface Emits" in scaffold
        assert "defineProps<Props>()" in scaffold
        assert "defineEmits<Emits>()" in scaffold
        assert "<template>" in scaffold
        assert "<style scoped>" in scaffold

    def test_handles_empty_props_and_emits(self):
        """Generate scaffold with no props/emits."""
        scaffold = _generate_vue_component_scaffold(
            component_name="SimplePanel",
            section_name="Simple",
            template_content="<div>Simple</div>",
            props=[],
            emits=[],
        )

        assert "No props detected" in scaffold
        assert "No emits detected" in scaffold


class TestGenerateComposableScaffold:
    """Tests for _generate_composable_scaffold helper."""

    def test_generates_composable(self):
        """Generate valid composable structure."""
        scaffold = _generate_composable_scaffold(
            composable_name="useFilter",
            refs=["searchQuery", "category"],
            reactives=["state"],
            computeds=["filteredItems"],
            functions=["applyFilter", "resetFilter"],
        )

        assert "export function useFilter()" in scaffold
        assert "searchQuery" in scaffold
        assert "state" in scaffold
        assert "filteredItems" in scaffold
        assert "applyFilter" in scaffold
        assert "return {" in scaffold

    def test_handles_empty_detection(self):
        """Generate scaffold with no detected elements."""
        scaffold = _generate_composable_scaffold(
            composable_name="useEmpty",
            refs=[],
            reactives=[],
            computeds=[],
            functions=[],
        )

        assert "export function useEmpty()" in scaffold
        assert "No refs detected" in scaffold


class TestHelperFunctions:
    """Tests for helper functions."""

    def test_to_pascal(self):
        """Convert to PascalCase."""
        assert _to_pascal("filter-bar") == "FilterBar"
        assert _to_pascal("header_section") == "HeaderSection"
        assert _to_pascal("simple name") == "SimpleName"
        assert _to_pascal("already") == "Already"

    def test_to_kebab(self):
        """Convert to kebab-case."""
        assert _to_kebab("FilterBar") == "filter-bar"
        assert _to_kebab("HeaderSection") == "header-section"
        assert _to_kebab("Simple") == "simple"
        assert _to_kebab("XMLParser") == "x-m-l-parser"
