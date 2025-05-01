# Workflow State & Rules (STM + Rules + Log)

*This file contains the dynamic state, embedded rules, active plan, and log for the current session.*
*It is read and updated frequently by the AI during its operational loop.*

---

## State

*Holds the current status of the workflow.*

```yaml
Phase: VALIDATE # Current workflow phase (ANALYZE, BLUEPRINT, CONSTRUCT, VALIDATE, BLUEPRINT_REVISE)
Status: COMPLETED # Current status (READY, IN_PROGRESS, BLOCKED_*, NEEDS_*, COMPLETED, COMPLETED_ITERATION)
CurrentTaskID: TwitterAutomationPipeline # Identifier for the main task being worked on
CurrentStep: null # Identifier for the specific step in the plan being executed
CurrentItem: null # Identifier for the item currently being processed in iteration
```

---

## Plan

*Contains the step-by-step implementation plan generated during the BLUEPRINT phase.*

**Task: TwitterAutomationPipeline**

*   `[✓] Step 1: Create project directory structure as specified in the requirements.`
*   `[✓] Step 2: Generate requirements.txt with all required dependencies.`
*   `[✓] Step 3: Create .gitignore file with appropriate entries.`
*   `[✓] Step 4: Create .env.example file for API credentials template.`
*   `[✓] Step 5: Create config/config.yaml with configuration settings.`
*   `[✓] Step 6: Implement src/config_loader.py for loading configuration.`
*   `[✓] Step 7: Implement src/utils.py with logging and retry functionality.`
*   `[✓] Step 8: Implement content sources modules (base_source.py and file_source.py).`
*   `[✓] Step 9: Implement src/content_processor.py for basic tweet formatting.`
*   `[✓] Step 10: Implement src/twitter_poster.py for API interaction.`
*   `[✓] Step 11: Implement src/scheduler.py for automated scheduling.`
*   `[✓] Step 12: Implement src/main.py as the entry point.`
*   `[✓] Step 13: Create sample data files for testing.`
*   `[✓] Step 14: Create comprehensive README.md with usage instructions.`
*   `[✓] Step 15: Simplify project as per user requirements.`
*   `[✓] Step 16: Further simplify by flattening directory structure and removing unnecessary components.`

---

## Rules

*Embedded rules governing the AI's autonomous operation.*

**# --- Core Workflow Rules ---**

RULE_WF_PHASE_ANALYZE:
  **Constraint:** Goal is understanding request/context. NO solutioning or implementation planning.

RULE_WF_PHASE_BLUEPRINT:
  **Constraint:** Goal is creating a detailed, unambiguous step-by-step plan. NO code implementation.

RULE_WF_PHASE_CONSTRUCT:
  **Constraint:** Goal is executing the `## Plan` exactly. NO deviation. If issues arise, trigger error handling or revert phase.

RULE_WF_PHASE_VALIDATE:
  **Constraint:** Goal is verifying implementation against `## Plan` and requirements using tools. NO new implementation.

RULE_WF_TRANSITION_01:
  **Trigger:** Explicit user command (`@analyze`, `@blueprint`, `@construct`, `@validate`).
  **Action:** Update `State.Phase` accordingly. Log phase change.

RULE_WF_TRANSITION_02:
  **Trigger:** AI determines current phase constraint prevents fulfilling user request OR error handling dictates phase change (e.g., RULE_ERR_HANDLE_TEST_01).
  **Action:** Log the reason. Update `State.Phase` (e.g., to `BLUEPRINT_REVISE`). Set `State.Status` appropriately (e.g., `NEEDS_PLAN_APPROVAL`). Report to user.

RULE_ITERATE_01: # Triggered by RULE_MEM_READ_STM_01 when State.Status == READY and State.CurrentItem == null, or after VALIDATE phase completion.
  **Trigger:** `State.Status == READY` and `State.CurrentItem == null` OR after `VALIDATE` phase completion.
  **Action:**
    1. Check `## Items` section for more items.
    2. If more items:
    3. Set `State.CurrentItem` to the next item.
    4. Clear `## Log`.
    5. Set `State.Phase = ANALYZE`, `State.Status = READY`.
    6. Log "Starting processing item [State.CurrentItem]".
    7. If no more items:
    8. Trigger `RULE_ITERATE_02`.

RULE_ITERATE_02:
  **Trigger:** `RULE_ITERATE_01` determines no more items.
  **Action:**
    1. Set `State.Status = COMPLETED_ITERATION`.
    2. Log "Tokenization iteration completed."

**# --- Initialization & Resumption Rules ---**

RULE_INIT_01:
  **Trigger:** AI session/task starts AND `workflow_state.md` is missing or empty.
  **Action:**
    1. Create `workflow_state.md` with default structure.
    2. Read `project_config.md` (prompt user if missing).
    3. Set `State.Phase = ANALYZE`, `State.Status = READY`.
    4. Log "Initialized new session."
    5. Prompt user for the first task.

RULE_INIT_02:
  **Trigger:** AI session/task starts AND `workflow_state.md` exists.
  **Action:**
    1. Read `project_config.md`.
    2. Read existing `workflow_state.md`.
    3. Log "Resumed session."
    4. Check `State.Status`: Handle READY, COMPLETED, BLOCKED_*, NEEDS_*, IN_PROGRESS appropriately (prompt user or report status).

RULE_INIT_03:
  **Trigger:** User confirms continuation via RULE_INIT_02 (for IN_PROGRESS state).
  **Action:** Proceed with the next action based on loaded state and rules.

**# --- Memory Management Rules ---**

RULE_MEM_READ_LTM_01:
  **Trigger:** Start of a new major task or phase.
  **Action:** Read `project_config.md`. Log action.
RULE_MEM_READ_STM_01:
  **Trigger:** Before *every* decision/action cycle.
  **Action:**
    1. Read `workflow_state.md`.
    2. If `State.Status == READY` and `State.CurrentItem == null`:
    3. Log "Attempting to trigger RULE_ITERATE_01".
    4. Trigger `RULE_ITERATE_01`.

RULE_MEM_UPDATE_STM_01:
  **Trigger:** After *every* significant action or information receipt.
  **Action:** Immediately update relevant sections (`## State`, `## Plan`, `## Log`) in `workflow_state.md` and save.

RULE_MEM_UPDATE_LTM_01:
  **Trigger:** User command (`@config/update`) OR end of successful VALIDATE phase for significant change.
  **Action:** Propose concise updates to `project_config.md` based on `## Log`/diffs. Set `State.Status = NEEDS_LTM_APPROVAL`. Await user confirmation.

RULE_MEM_VALIDATE_01:
  **Trigger:** After updating `workflow_state.md` or `project_config.md`.
  **Action:** Perform internal consistency check. If issues found, log and set `State.Status = NEEDS_CLARIFICATION`.

**# --- Tool Integration Rules (Cursor Environment) ---**

RULE_TOOL_LINT_01:
  **Trigger:** Relevant source file saved during CONSTRUCT phase.
  **Action:** Instruct Cursor terminal to run lint command. Log attempt. On completion, parse output, log result, set `State.Status = BLOCKED_LINT` if errors.

RULE_TOOL_FORMAT_01:
  **Trigger:** Relevant source file saved during CONSTRUCT phase.
  **Action:** Instruct Cursor to apply formatter or run format command via terminal. Log attempt.

RULE_TOOL_TEST_RUN_01:
  **Trigger:** Command `@validate` or entering VALIDATE phase.
  **Action:** Instruct Cursor terminal to run test suite. Log attempt. On completion, parse output, log result, set `State.Status = BLOCKED_TEST` if failures, `TESTS_PASSED` if success.

RULE_TOOL_APPLY_CODE_01:
  **Trigger:** AI determines code change needed per `## Plan` during CONSTRUCT phase.

RULE_PROCESS_ITEM_01:
  **Trigger:** `State.Phase == CONSTRUCT` and `State.CurrentItem` is not null and current step in `## Plan` requires item processing.
  **Action:**
    1. **Get Item Text:** Based on `State.CurrentItem`, extract the corresponding 'Text to Tokenize' from the `## Items` section.
    2. **Summarize (Placeholder):**  Use a placeholder to generate a summary of the extracted text.  For example, "Summary of [text] is [placeholder summary]".
    3. **Estimate Token Count:**
       a. Read `Characters Per Token (Estimate)` from `project_config.md`.
       b. Get the text content of the item from the `## Items` section. (Placeholder: Implement logic to extract text based on `State.CurrentItem` from the `## Items` table.)
       c. Calculate `estimated_tokens = length(text_content) / 4`.
    4. **Summarize (Placeholder):** Use a placeholder to generate a summary of the extracted text.  For example, "Summary of [text] is [placeholder summary]". (Placeholder: Replace with actual summarization tool/logic)
    5. **Store Results:** Append a new row to the `## TokenizationResults` table with:
       *   `Item ID`: `State.CurrentItem`
       *   `Summary`: The generated summary. (Placeholder: Implement logic to store the summary.)
       *   `Token Count`: `estimated_tokens`.
    6. Log the processing actions, results, and estimated token count to the `## Log`. (Placeholder: Implement logging.)

  **Action:** Generate modification. Instruct Cursor to apply it. Log action.

**# --- Error Handling & Recovery Rules ---**

RULE_ERR_HANDLE_LINT_01:
  **Trigger:** `State.Status` is `BLOCKED_LINT`.
  **Action:** Analyze error in `## Log`. Attempt auto-fix if simple/confident. Apply fix via RULE_TOOL_APPLY_CODE_01. Re-run lint via RULE_TOOL_LINT_01. If success, reset `State.Status`. If fail/complex, set `State.Status = BLOCKED_LINT_UNRESOLVED`, report to user.

RULE_ERR_HANDLE_TEST_01:
  **Trigger:** `State.Status` is `BLOCKED_TEST`.
  **Action:** Analyze failure in `## Log`. Attempt auto-fix if simple/localized/confident. Apply fix via RULE_TOOL_APPLY_CODE_01. Re-run failed test(s) or suite via RULE_TOOL_TEST_RUN_01. If success, reset `State.Status`. If fail/complex, set `State.Phase = BLUEPRINT_REVISE`, `State.Status = NEEDS_PLAN_APPROVAL`, propose revised `## Plan` based on failure analysis, report to user.

RULE_ERR_HANDLE_GENERAL_01:
  **Trigger:** Unexpected error or ambiguity.
  **Action:** Log error/situation to `## Log`. Set `State.Status = BLOCKED_UNKNOWN`. Report to user, request instructions.

---

## Log

*A chronological log of significant actions, events, tool outputs, and decisions.*
*(This section will be populated by the AI during operation)*

*   `[2023-08-11 10:00:00] Initialized new session. State set to ANALYZE/READY.`
*   `[2023-08-11 10:00:15] Read project_config.md - Twitter automation pipeline project details loaded.`
*   `[2023-08-11 10:00:30] Analyzing requirements for Twitter automation pipeline project.`
*   `[2023-08-11 10:01:00] Identified key components: content sourcing, processing, scheduling, and Twitter API integration.`
*   `[2023-11-10 14:00:00] Project simplification requested by user - removing RSS sources, UTM tracking, and complex content formatting.`
*   `[2023-11-10 14:30:00] Removed RSS source functionality.`
*   `[2023-11-10 14:45:00] Simplified content processor to basic title + URL format.`
*   `[2023-11-11 09:00:00] Further simplified project structure - removed URL appending, simplified to tweet-only content.`
*   `[2023-11-11 09:30:00] Reduced CSV structure to only tweet and is_posted columns.`
*   `[2023-11-11 10:00:00] Renamed fields for clarity (title->tweet, used->is_posted).`
*   `[2023-11-12 11:00:00] Aggressively simplified the codebase - eliminated the content_sources module structure.`
*   `[2023-11-12 11:15:00] Removed base_source.py and file_source.py, replaced with a single flat file_content_source.py.`
*   `[2023-11-12 11:30:00] Moved file_content_source.py to src directory for a flatter structure.`
*   `[2023-11-12 11:45:00] Simplified CSV handling - removed JSON support, streamlined error handling.`
*   `[2023-11-12 12:00:00] Updated imports in scheduler.py to use the new file structure.`
*   `[2023-11-12 12:15:00] Reduced content_processor.py to minimal implementation.`
*   `[2023-11-12 12:30:00] Removed test code sections from all modules.`
*   `[2023-11-12 13:00:00] Updated project documentation to reflect the new simplified structure.`

---

## Items

*This section will contain the list of items to be processed.*
*(The format of items is a table)*

| Item ID | Component | Description | Status |
|---|---|---|---|
| component1 | Project Structure | Create directories and initial empty files | COMPLETED |
| component2 | Configuration | Create config.yaml and .env.example | COMPLETED |
| component3 | Content Sources | Implement file-based content source | COMPLETED |
| component4 | Content Processing | Implement basic tweet formatting | COMPLETED |
| component5 | Twitter Integration | Implement Twitter API authentication and posting | COMPLETED |
| component6 | Scheduling | Implement scheduling and queue management | COMPLETED |
| component7 | Documentation | Create README and usage instructions | COMPLETED |
| component8 | Simplification | Remove RSS, UTM tracking, and complex formatting | COMPLETED |

---

## TokenizationResults

*This section will store the results for each component development.*
*(Results will include completion status and notes)*

| Component ID | Status | Notes |
|---|---|---|
| component1 | COMPLETED | Project structure created with all required directories and files |
| component2 | COMPLETED | Configuration files created with simplified settings |
| component3 | COMPLETED | File-based content source implemented (CSV format) |
| component4 | COMPLETED | Simple content processor implemented (title + URL format) |
| component5 | COMPLETED | Twitter integration with proper API handling and rate limiting |
| component6 | COMPLETED | Scheduling implemented with interval and specific time options |
| component7 | COMPLETED | Comprehensive README with setup and usage instructions |
| component8 | COMPLETED | Successfully simplified the project as requested |
| component9 | COMPLETED | Added helper scripts for streamlined usage (setup.sh and run.sh) |
| component10 | COMPLETED | Successfully tested end-to-end with live posting to X/Twitter | 