# Chat Tabs and Session Lifecycle Implementation Plan

**Goal:** Separate Quick Chat and Research Agent into explicit tabs and make session creation, selection, persistence status, and export discoverable.

## Frontend state

1. Refactor `useNotebookChat` to keep current session IDs and pending model overrides by mode.
2. Add `startNewSession()` that clears the active mode locally without creating an empty server record.
3. Expose save status based on stream and session synchronization lifecycle.
4. Keep Quick/Research drafts and web-search settings independently in ChatPanel.

## UI

1. Replace mode checkboxes with notebook-only Tabs in ChatPanel header.
2. Add a compact current-session dropdown, explicit new-session icon, and existing management dialog entry.
3. Render mode-specific bottom controls: Quick web/model; Research web/cross-notebook/model.
4. Add Markdown export for the current visible session.
5. Preserve source-chat layout and behavior.

## Verification

1. Hook tests cover per-mode session restoration, local new-session drafts, first-message creation, and save states.
2. Component tests cover Tabs, mode-specific controls, session dropdown/new/export actions, and source-chat regression.
3. Run targeted and full Vitest, ESLint, production build, and `git diff --check`.
4. Update `docs/8-CUSTOMIZATION/00-index.md` with behavior and actual validation.
