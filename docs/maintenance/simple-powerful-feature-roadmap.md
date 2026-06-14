# Simple Powerful Feature Roadmap

Date: 2026-06-15

## Purpose

YDManager should become stronger by making video exploration faster, safer, and easier to continue.

The product direction is intentionally simple:

- do not add many visible panels;
- do not create a complicated tagging system;
- do not turn the app into a media suite;
- prioritize fast recognition, fast playback transition, and safe organization.

The core user value remains:

> Explore many videos quickly without waiting, losing context, or accidentally damaging the collection.

## Design Principles

### Keep The First Screen Work-Focused

The main screen should stay a fast explorer/player, not a dashboard.

New capabilities should appear through:

- better list state;
- better preview data;
- keyboard commands;
- small status indicators;
- context menus only where needed.

Avoid adding large decorative cards, extra tabs, or heavy modal workflows.

### Make Powerful Features Feel Passive

The strongest features should work in the background:

- thumbnails are already cached;
- session state is already restored;
- preload metrics are already collected;
- recently changed files are already recoverable.

The user should feel the app is faster and safer without needing to manage settings constantly.

### Prefer Few Concepts

Keep user-facing concepts small:

- video;
- current watch session;
- candidate row;
- tag A/B;
- highlight;
- trash;
- queue/state;
- history.

Do not introduce many labels, nested collections, ratings, albums, or timeline objects until the basic workflow proves it needs them.

## Priority Roadmap

## 1. Thumbnail Timeline Cache

### Goal

Let the user understand a video before opening it.

### Minimal Feature

For each indexed video, generate a small strip of scene thumbnails:

- 6 thumbnails for short clips;
- 8-12 thumbnails for longer videos;
- stored in an app cache, not beside the source video;
- generated lazily in the background;
- invalidated when file path, size, or modified time changes.

### UI Shape

Keep it restrained:

- show a compact thumbnail strip in the right-side player area when a row is selected but not playing;
- show the strip in highlight/detail context;
- optionally show one preview thumbnail in the list only if performance stays good.

### Why It Matters

This is the strongest improvement for fast exploration. It reduces unnecessary playback opens and lets the user classify videos faster.

### Avoid

- full video preview grids;
- large poster cards;
- always-on animated previews;
- storing generated files in the media folder.

## 2. Complete Session Restore

### Goal

The app should resume exactly where the user left off.

### Minimal Feature

Persist and restore:

- last root folder;
- current view mode;
- search text;
- selected row;
- active watch path;
- playback position;
- playback rate;
- audio enabled state;
- autoscan enabled state;
- window geometry.

### Rules

- If the saved video no longer exists, restore the folder and candidate row only.
- If the saved path exists, restore it without forcing an unwanted playback start when autoplay is off.
- If privacy mode is on, restore state without exposing the video frame until allowed.

### Why It Matters

This makes the app feel stable and professional. It also protects long sorting sessions from interruption.

## 3. Smart Exploration Queue

### Goal

Help the user decide what to review next without creating complex tag management.

### Minimal Queue States

Use a small fixed state model:

- `unreviewed`
- `kept`
- `hold`
- `delete_candidate`
- `has_highlight`
- `recently_viewed`

This should be internal metadata first. It does not need a large UI.

### UI Shape

Expose as a simple segmented filter or command palette query:

- All
- Unreviewed
- Kept
- Hold
- Delete Candidates
- Highlights

### Why It Matters

A/B tags are useful, but sorting work needs a stronger workflow state. A queue makes large collections manageable.

### Avoid

- arbitrary nested categories;
- many custom tag colors;
- folder-like virtual albums in the first version.

## 4. Undoable Action History

### Goal

Make organization safer.

### Minimal Feature

Track recent reversible actions:

- soft delete;
- restore;
- tag A/B change;
- highlight add/delete;
- hash rename.

Expose:

- `Ctrl+Z` for the most recent reversible action;
- a compact recent-actions list in settings or a small command palette view.

### Rules

- Hard delete is not reversible unless the file still exists elsewhere.
- Undo should fail safely with a clear message if the source file changed externally.
- Action records should be stored in app data, not source folders.

### Why It Matters

Fast sorting creates mistakes. Undo makes speed safer.

## 5. Command Palette

### Goal

Add power without adding visible UI clutter.

### Minimal Feature

Open with one shortcut and support commands like:

```text
tag:a
tag:b
highlight
trash
mode:main
mode:trash
queue:unreviewed
name:yujin
duration>3m
```

### Rules

- The command palette should reuse existing search infrastructure where possible.
- It should not replace normal search in the first version.
- Commands must preview their effect before destructive operations.

### Why It Matters

The app becomes much faster for keyboard-heavy users without adding panels or buttons.

## 6. Duplicate And Near-Duplicate Detection

### Goal

Help remove waste from large collections.

### Minimal Feature

Start with safe exact duplicate detection:

- file size;
- content hash;
- duration if available.

Later add near-duplicate candidates:

- same duration;
- similar basename;
- same dimensions;
- similar thumbnail hash.

### UI Shape

Keep it as a review queue:

- show duplicate group;
- let user keep one;
- send others to trash candidate state.

### Avoid

- automatic deletion;
- aggressive near-duplicate decisions;
- blocking the UI while hashing.

## 7. Playback Performance Telemetry

### Goal

Make the player engine measurable so future optimization is evidence-based.

### Minimal Metrics

Collect locally:

- activation path;
- preload hit or miss;
- activation-to-visible-frame time;
- fallback reveal count;
- media error count by path;
- stale signal suppression count;
- passive refresh replan count.

### UI Shape

No main-screen UI at first.

Expose a diagnostics export or a small settings/debug panel only when needed.

### Why It Matters

The app's core promise is fast video exploration. Without metrics, future performance work becomes guesswork.

## Recommended Implementation Order

1. Playback performance telemetry
2. Complete session restore
3. Thumbnail timeline cache
4. Smart exploration queue
5. Undoable action history
6. Command palette
7. Duplicate detection

This order is slightly different from user-visible impact because telemetry makes the later performance work safer, and session restore is a low-clutter quality upgrade.

## First Build Candidate

The best next implementation candidate is:

> Complete session restore plus lightweight playback telemetry.

Reason:

- low UI complexity;
- improves reliability immediately;
- creates measurement data for thumbnail and preload work;
- fits the current Player Engine v3/v4 architecture.

The best next high-impact user-visible candidate after that is:

> Thumbnail timeline cache.

## Non-Goals For The Next Phase

Do not implement these yet:

- AI auto-tagging;
- face recognition;
- online metadata lookup;
- cloud sync;
- complex custom tag taxonomy;
- timeline video editing;
- automatic deletion.

These may be useful later, but they would make the app feel heavier before the core explorer workflow is fully polished.

## Acceptance Standard For Future Features

Every new feature should pass this checklist:

- It makes video exploration faster, safer, or easier to resume.
- It does not add a large permanent UI surface.
- It does not bypass `PlayerEngine` for media loading.
- It works with A/B tags, highlights, trash, search, and passive menu continuity.
- It has focused tests before implementation.
- It can be disabled or ignored without harming the core player.
