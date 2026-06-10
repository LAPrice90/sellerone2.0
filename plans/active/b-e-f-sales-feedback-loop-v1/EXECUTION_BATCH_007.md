# Execution Batch 007

## Title
- Sold-product truth-first accuracy pack

## Job
- make products we actually sold the primary accuracy test set.
- measure how wrong current demand, profit, and pass/fail logic are before trusting the price-list ordering path.

## Allowed files to change
- `scripts/one_off/F011_build_sales_history_accuracy_pack.py`
- `scripts/one_off/BEF003_build_sales_feedback_examples.py`
- `scripts/one_off/F012_build_sales_history_learning_pack.py`
- `scripts/one_off/BEF004_run_sales_feedback_guarded_once.py`
- `tests/test_f011_build_sales_history_accuracy_pack.py`
- `tests/test_bef003_build_sales_feedback_examples.py`
- `tests/test_f012_build_sales_history_learning_pack.py`
- `tests/test_bef004_run_sales_feedback_guarded_once.py`
- `plans/active/b-e-f-sales-feedback-loop-v1/CODING_PLAN.md`
- `plans/active/b-e-f-sales-feedback-loop-v1/PLAN_STATUS.md`
- `plans/active/b-e-f-sales-feedback-loop-v1/EXECUTION_BATCH_007.md`

## Expectations

### Output 1 - sold-product truth set
- build a primary accuracy universe from products we actually sold, not from unsold supplier scans.
- actual units and profit must come from B/E truth only:
  - `sku_daily_sales_truth_latest.csv`
  - `order_ledger_fx.csv`
  - related operational truth outputs
- no manual operator actual-sales entry is allowed for the normal path.

### Output 2 - replay what the model would have said
- for each sold product, capture the best available model-side estimate and decision evidence:
  - estimated demand
  - estimated profit
  - decision state
  - decision confidence
- if estimate-side evidence is missing, keep that explicit as a coverage gap, not a silent drop.

### Output 3 - accuracy measurement
- produce an accuracy pack that answers business questions directly:
  - false pass count
  - false fail count
  - demand overestimate count
  - demand underestimate count
  - profit overestimate count
  - profit underestimate count
- separate:
  - rows with enough evidence to judge accuracy
  - rows missing model-side evidence
  - rows missing sold-truth evidence

### Output 4 - operator-ready business view
- produce examples and summary rows in plain language so we can see:
  - what types of products the model is overrating
  - what types of products the model is underrating
  - whether the current logic is safe enough to use before ordering from the price list

## Tests required
- `python -m py_compile scripts/one_off/F011_build_sales_history_accuracy_pack.py scripts/one_off/BEF003_build_sales_feedback_examples.py scripts/one_off/F012_build_sales_history_learning_pack.py scripts/one_off/BEF004_run_sales_feedback_guarded_once.py tests/test_f011_build_sales_history_accuracy_pack.py tests/test_bef003_build_sales_feedback_examples.py tests/test_f012_build_sales_history_learning_pack.py tests/test_bef004_run_sales_feedback_guarded_once.py`
- `pytest tests/test_f011_build_sales_history_accuracy_pack.py tests/test_bef003_build_sales_feedback_examples.py tests/test_f012_build_sales_history_learning_pack.py tests/test_bef004_run_sales_feedback_guarded_once.py -q`
- runtime proof:
  - `python scripts/one_off/F011_build_sales_history_accuracy_pack.py`
  - `python scripts/one_off/BEF004_run_sales_feedback_guarded_once.py`

## Proof required
- show these together:
  - total sold-product rows included
  - sold-product rows with model-side evidence
  - sold-product rows missing model-side evidence
  - false pass count
  - false fail count
  - top 5 error buckets by row count
  - whether current evidence is strong enough to trust ordering decisions yet

## Success definition
- `code fix applied`:
  - sold-product truth is now the main accuracy input
- `isolated verification passed`:
  - compile and pytest pass for batch scope
- `live loop verification confirmed`:
  - one-off builders run successfully and guarded output stays truthful
- phase success threshold:
  - nonzero sold-product accuracy rows
  - nonzero judged accuracy rows
  - explicit false pass / false fail metrics produced
  - no manual actual-sales entry required

## Timeout rule
- if sold-product rows exist but model-side evidence is still too thin:
  - park as `parked pending sold-truth replay coverage expansion`
  - keep the sold-product report as the primary truth artifact anyway
  - do not revert to unsold scans as the main accuracy proof

## Sign-off format
- `code fix applied: yes/no`
- `isolated verification passed: yes/no`
- `live loop verification confirmed: yes/no`

## Next step after sign-off
- use the sold-product error classes to decide which buying rules to tighten first:
  - demand floor
  - profit floor
  - seasonality handling
  - Amazon / price pressure handling

## Execution result (2026-04-21)
- implementation status:
  - complete with warning state
- code changes applied:
  - `scripts/one_off/F011_build_sales_history_accuracy_pack.py`
  - `tests/test_f011_build_sales_history_accuracy_pack.py`
- tests:
  - compile command in this batch -> pass
  - pytest command in this batch -> pass (`18 passed`)
- runtime proof:
  - `python scripts/one_off/F011_build_sales_history_accuracy_pack.py` -> pass at `2026-04-21T12:24:43Z`
  - `python scripts/one_off/BEF004_run_sales_feedback_guarded_once.py` -> pass at `2026-04-21T12:24:51Z`
  - guarded state:
    - `guard_status=ready`
    - `readiness_label=ready_with_warnings`
- proof metrics:
  - `sold_rows_total=57`
  - `sold_rows_with_model_side_evidence=19`
  - `sold_rows_missing_model_side_evidence=38`
  - `judged_accuracy_rows=19`
  - `false_pass_rows=0`
  - `false_fail_rows=0`
  - top 5 error buckets:
    - `missing_model_decision:57`
    - `missing_model_estimate:38`
    - `missing_model_side_evidence:38`
    - `profit_underestimate:16`
    - `profit_underestimate_severe:15`
- sign-off state:
  - `code fix applied: yes`
  - `isolated verification passed: yes`
  - `live loop verification confirmed: yes`
- timeout-rule disposition:
  - `parked pending sold-truth replay coverage expansion`
