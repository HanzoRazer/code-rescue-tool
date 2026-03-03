; js_ts_security.scm — Tree-sitter query for JS/TS security patterns.
;
; Governed by rules_registry.json — changes here MUST be followed by:
;   python scripts/refresh_rules_registry.py
;
; signal_logic_version: signals_v5

; SEC_EVAL_JS_001 — eval(...)
(call_expression
  function: (identifier) @sec_eval.callee
  (#eq? @sec_eval.callee "eval"))

; SEC_NEW_FUNCTION_JS_001 — new Function(...)
(new_expression
  constructor: (identifier) @sec_new_function.ctor
  (#eq? @sec_new_function.ctor "Function"))

; EXC_EMPTY_CATCH_JS_001 — empty catch block
(catch_clause
  body: (statement_block) @exc_empty_catch.body)

; GST_GLOBAL_THIS_MUTATION_001 — globalThis.x = ... / window.x = ...
(assignment_expression
  left: (member_expression
    object: (identifier) @gst_global_mutation.obj
    property: (property_identifier) @gst_global_mutation.prop))

; SEC_DYNAMIC_MODULE_LOAD_JS_001 — require(<non-literal>) / import(<non-literal>)
(call_expression
  function: (identifier) @sec_dyn_load.fn
  arguments: (arguments) @sec_dyn_load.args)
