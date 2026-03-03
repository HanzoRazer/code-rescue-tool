"""Tests for VueCouplingFixer."""

import pytest

from code_rescue.fixers.vue_coupling import (
    VueCouplingFixer,
    generate_composable_from_concern,
    list_known_concerns,
)
from code_rescue.fixers.base import FixStatus
from code_rescue.model.rescue_action import ActionType, RescueAction, SafetyLevel


# ══════════════════════════════════════════════════════════════════════════════
# Test Data
# ══════════════════════════════════════════════════════════════════════════════

SELECTION_COMPONENT = """<script setup lang="ts">
import { ref, computed } from 'vue'

const selectedIds = ref<Set<string>>(new Set())
const items = ref([])

function toggleSelection(id: string) {
  if (selectedIds.value.has(id)) {
    selectedIds.value.delete(id)
  } else {
    selectedIds.value.add(id)
  }
}
</script>
"""

MIXED_CONCERNS_COMPONENT = """<script setup lang="ts">
import { ref, onMounted } from 'vue'

// Data fetching
const data = ref(null)
const loading = ref(false)

async function fetchData() {
  loading.value = true
  const response = await fetch('/api/data')
  data.value = await response.json()
  loading.value = false
}

// Form handling
const formData = ref({})
const errors = ref({})

function validateForm() {
  errors.value = {}
}

onMounted(fetchData)
</script>
"""

EXCESSIVE_PROPS_COMPONENT = """<script setup lang="ts">
defineProps<{
  userId: string;
  userName: string;
  userEmail: string;
  userRole: string;
  userAvatar: string;
  configMode: string;
  configOptions: object;
  styleClass: string;
  styleTheme: string;
  otherA: string;
  otherB: string;
  otherC: string;
}>()
</script>
"""


# ══════════════════════════════════════════════════════════════════════════════
# Tests: Fixer Protocol
# ══════════════════════════════════════════════════════════════════════════════


class TestVueCouplingFixerProtocol:
    """Tests for fixer protocol compliance."""

    def test_supported_rules(self):
        fixer = VueCouplingFixer()
        assert "VUE-COMPOSE-001" in fixer.supported_rules
        assert "VUE-COMPOSE-002" in fixer.supported_rules
        assert "VUE-COUPLE-001" in fixer.supported_rules
        assert "VUE-COUPLE-002" in fixer.supported_rules
        assert "VUE-COUPLE-003" in fixer.supported_rules
        assert "VUE-COUPLE-004" in fixer.supported_rules

    def test_can_fix_supported_rules(self):
        fixer = VueCouplingFixer()

        for rule_id in fixer.supported_rules:
            action = RescueAction(
                action_id="test",
                finding_id="test",
                rule_id=rule_id,
                action_type=ActionType.EXTRACT,
                safety_level=SafetyLevel.MANUAL,
                description="test",
                file_path="Component.vue",
                line_start=1,
                line_end=10,
            )
            assert fixer.can_fix(action) is True

    def test_cannot_fix_unsupported_rules(self):
        fixer = VueCouplingFixer()

        action = RescueAction(
            action_id="test",
            finding_id="test",
            rule_id="UNKNOWN-001",
            action_type=ActionType.EXTRACT,
            safety_level=SafetyLevel.MANUAL,
            description="test",
            file_path="Component.vue",
            line_start=1,
            line_end=10,
        )
        assert fixer.can_fix(action) is False


# ══════════════════════════════════════════════════════════════════════════════
# Tests: State Group Composable (VUE-COMPOSE-001)
# ══════════════════════════════════════════════════════════════════════════════


class TestStateGroupComposable:
    """Tests for VUE-COMPOSE-001 fix generation."""

    def test_generates_selection_composable_from_known_concern(self):
        fixer = VueCouplingFixer()

        action = RescueAction(
            action_id="test",
            finding_id="test",
            rule_id="VUE-COMPOSE-001",
            action_type=ActionType.EXTRACT,
            safety_level=SafetyLevel.MANUAL,
            description="Extract selection state",
            file_path="Component.vue",
            line_start=1,
            line_end=15,
            metadata={
                "suggested_composable": "useSelection",
                "refs": ["selectedIds", "selectedItems"],
                "group_concern": "selection",
            },
        )

        scaffold, rationale = fixer.generate_fix(action, SELECTION_COMPONENT)

        assert scaffold is not None
        assert "useSelection" in scaffold
        assert "toggle" in scaffold
        assert "selectAll" in scaffold
        assert rationale is not None
        assert "selection" in rationale.lower()

    def test_generates_generic_composable_for_unknown_concern(self):
        fixer = VueCouplingFixer()

        action = RescueAction(
            action_id="test",
            finding_id="test",
            rule_id="VUE-COMPOSE-001",
            action_type=ActionType.EXTRACT,
            safety_level=SafetyLevel.MANUAL,
            description="Extract custom state",
            file_path="Component.vue",
            line_start=1,
            line_end=15,
            metadata={
                "suggested_composable": "useCustom",
                "refs": ["stateA", "stateB"],
                "group_concern": "custom_unknown",
            },
        )

        scaffold, rationale = fixer.generate_fix(action, SELECTION_COMPONENT)

        assert scaffold is not None
        assert "useCustom" in scaffold
        assert "stateA" in scaffold
        assert "stateB" in scaffold


# ══════════════════════════════════════════════════════════════════════════════
# Tests: Concern Separation (VUE-COMPOSE-002)
# ══════════════════════════════════════════════════════════════════════════════


class TestConcernSeparation:
    """Tests for VUE-COMPOSE-002 fix generation."""

    def test_generates_separation_hints_for_multiple_concerns(self):
        fixer = VueCouplingFixer()

        action = RescueAction(
            action_id="test",
            finding_id="test",
            rule_id="VUE-COMPOSE-002",
            action_type=ActionType.REFACTOR,
            safety_level=SafetyLevel.MANUAL,
            description="Separate concerns",
            file_path="MixedComponent.vue",
            line_start=1,
            line_end=30,
            metadata={
                "concerns": ["data_fetching", "form_handling"],
            },
        )

        hint, rationale = fixer.generate_fix(action, MIXED_CONCERNS_COMPONENT)

        assert hint is not None
        assert "data_fetching" in hint
        assert "form_handling" in hint
        assert "useFetch" in hint
        assert "useForm" in hint
        assert rationale is not None
        assert "2 concerns" in rationale

    def test_no_hints_for_empty_concerns(self):
        fixer = VueCouplingFixer()

        action = RescueAction(
            action_id="test",
            finding_id="test",
            rule_id="VUE-COMPOSE-002",
            action_type=ActionType.REFACTOR,
            safety_level=SafetyLevel.MANUAL,
            description="Separate concerns",
            file_path="Component.vue",
            line_start=1,
            line_end=10,
            metadata={
                "concerns": [],
            },
        )

        hint, rationale = fixer.generate_fix(action, "")

        assert hint is None


# ══════════════════════════════════════════════════════════════════════════════
# Tests: Props Restructuring (VUE-COUPLE-001)
# ══════════════════════════════════════════════════════════════════════════════


class TestPropsRestructuring:
    """Tests for VUE-COUPLE-001 fix generation."""

    def test_generates_restructuring_plan(self):
        fixer = VueCouplingFixer()

        action = RescueAction(
            action_id="test",
            finding_id="test",
            rule_id="VUE-COUPLE-001",
            action_type=ActionType.REFACTOR,
            safety_level=SafetyLevel.MANUAL,
            description="Excessive props",
            file_path="Component.vue",
            line_start=1,
            line_end=15,
            metadata={
                "prop_count": 12,
                "props": [
                    "userId", "userName", "userEmail", "userRole", "userAvatar",
                    "configMode", "configOptions",
                    "styleClass", "styleTheme",
                    "otherA", "otherB", "otherC",
                ],
            },
        )

        hint, rationale = fixer.generate_fix(action, EXCESSIVE_PROPS_COMPONENT)

        assert hint is not None
        assert "Props Restructuring" in hint
        assert "12 individual props" in hint
        assert "provide/inject" in hint.lower() or "Provide/Inject" in hint
        assert rationale is not None
        assert "12 props" in rationale


# ══════════════════════════════════════════════════════════════════════════════
# Tests: Emit Consolidation (VUE-COUPLE-002)
# ══════════════════════════════════════════════════════════════════════════════


class TestEmitConsolidation:
    """Tests for VUE-COUPLE-002 fix generation."""

    def test_generates_consolidation_plan(self):
        fixer = VueCouplingFixer()

        action = RescueAction(
            action_id="test",
            finding_id="test",
            rule_id="VUE-COUPLE-002",
            action_type=ActionType.REFACTOR,
            safety_level=SafetyLevel.MANUAL,
            description="Excessive emits",
            file_path="Component.vue",
            line_start=1,
            line_end=15,
            metadata={
                "emit_count": 8,
                "emits": [
                    "create", "update", "delete", "save",
                    "open", "close", "toggle", "show",
                ],
            },
        )

        hint, rationale = fixer.generate_fix(action, "")

        assert hint is not None
        assert "Event Consolidation" in hint
        assert "8 individual emit events" in hint
        assert "v-model" in hint.lower()
        assert rationale is not None


# ══════════════════════════════════════════════════════════════════════════════
# Tests: High Coupling (VUE-COUPLE-003)
# ══════════════════════════════════════════════════════════════════════════════


class TestHighCoupling:
    """Tests for VUE-COUPLE-003 fix generation."""

    def test_generates_coupling_reduction_plan(self):
        fixer = VueCouplingFixer()

        action = RescueAction(
            action_id="test",
            finding_id="test",
            rule_id="VUE-COUPLE-003",
            action_type=ActionType.REFACTOR,
            safety_level=SafetyLevel.MANUAL,
            description="High coupling",
            file_path="Layout.vue",
            line_start=1,
            line_end=20,
            metadata={
                "import_count": 7,
                "component_imports": [
                    "HeaderPanel", "SidebarPanel", "ContentPanel",
                    "FooterPanel", "NavPanel", "ToolbarPanel", "StatusBar",
                ],
            },
        )

        hint, rationale = fixer.generate_fix(action, "")

        assert hint is not None
        assert "Coupling Reduction" in hint
        assert "7 direct component imports" in hint
        assert "slot" in hint.lower() or "Slot" in hint
        assert rationale is not None


# ══════════════════════════════════════════════════════════════════════════════
# Tests: Prop Drilling (VUE-COUPLE-004)
# ══════════════════════════════════════════════════════════════════════════════


class TestPropDrilling:
    """Tests for VUE-COUPLE-004 fix generation."""

    def test_generates_prop_drilling_fix(self):
        fixer = VueCouplingFixer()

        action = RescueAction(
            action_id="test",
            finding_id="test",
            rule_id="VUE-COUPLE-004",
            action_type=ActionType.REFACTOR,
            safety_level=SafetyLevel.MANUAL,
            description="Prop drilling",
            file_path="MiddleComponent.vue",
            line_start=1,
            line_end=20,
            metadata={
                "drilled_props": ["userId", "userName", "userRole", "locale"],
                "used_props": ["theme"],
                "depth_estimate": "3+ levels",
            },
        )

        hint, rationale = fixer.generate_fix(action, "")

        assert hint is not None
        assert "Prop Drilling" in hint
        assert "provide" in hint.lower()
        assert "inject" in hint.lower()
        assert rationale is not None
        assert "4 props" in rationale


# ══════════════════════════════════════════════════════════════════════════════
# Tests: Apply Method
# ══════════════════════════════════════════════════════════════════════════════


class TestApplyMethod:
    """Tests for the apply method."""

    def test_apply_returns_success_for_supported_rule(self):
        fixer = VueCouplingFixer()

        action = RescueAction(
            action_id="test",
            finding_id="test",
            rule_id="VUE-COMPOSE-001",
            action_type=ActionType.EXTRACT,
            safety_level=SafetyLevel.MANUAL,
            description="Extract state",
            file_path="Component.vue",
            line_start=1,
            line_end=15,
            metadata={
                "suggested_composable": "useSelection",
                "refs": ["selected"],
                "group_concern": "selection",
            },
        )

        result = fixer.apply(action, SELECTION_COMPONENT, dry_run=True)

        assert result.status == FixStatus.SUCCESS
        assert "scaffold" in result.message.lower()
        assert result.original_content == SELECTION_COMPONENT
        assert result.modified_content is None  # Vue fixes don't modify source

    def test_apply_returns_skipped_for_unsupported_rule(self):
        fixer = VueCouplingFixer()

        action = RescueAction(
            action_id="test",
            finding_id="test",
            rule_id="UNKNOWN-RULE",
            action_type=ActionType.REFACTOR,
            safety_level=SafetyLevel.MANUAL,
            description="Unknown",
            file_path="Component.vue",
            line_start=1,
            line_end=10,
        )

        result = fixer.apply(action, "", dry_run=True)

        assert result.status == FixStatus.SKIPPED


# ══════════════════════════════════════════════════════════════════════════════
# Tests: Utility Functions
# ══════════════════════════════════════════════════════════════════════════════


class TestUtilityFunctions:
    """Tests for standalone utility functions."""

    def test_list_known_concerns(self):
        concerns = list_known_concerns()

        assert "data_fetching" in concerns
        assert "form_handling" in concerns
        assert "pagination" in concerns
        assert "selection" in concerns
        assert "undo_redo" in concerns
        assert "modal_state" in concerns

    def test_generate_composable_from_known_concern(self):
        scaffold = generate_composable_from_concern("selection")

        assert scaffold is not None
        assert "useSelection" in scaffold
        assert "toggle" in scaffold
        assert "selectAll" in scaffold

    def test_generate_composable_from_unknown_concern(self):
        scaffold = generate_composable_from_concern("unknown_thing")

        assert scaffold is None

    def test_all_known_concerns_have_valid_templates(self):
        for concern in list_known_concerns():
            scaffold = generate_composable_from_concern(concern)
            assert scaffold is not None, f"Missing template for {concern}"
            assert "export function" in scaffold, f"Invalid template for {concern}"
