# Claude Code Style Tool Display

## Current Steve Code vs Claude Code

### Claude Code Style
```
● Let me read the interactive.py file to understand the structure:

● Read(src/ai_code_assistant/interactive.py)
  ⎿  Read 30 lines (ctrl+r to expand)

● Now I'll update the file to add the new feature:

● Update(src/ai_code_assistant/interactive.py)
╭─────────────────────────────────────────────────────────────────╮
│ Edit file                                                        │
│ ╭───────────────────────────────────────────────────────────────╮│
│ │ src/ai_code_assistant/interactive.py                         ││
│ │                                                               ││
│ │   289 -     def old_method(self):                             ││
│ │   290 -         return "old"                                  ││
│ │   291 +     def new_method(self):                             ││
│ │   292 +         return "new"                                  ││
│ ╰───────────────────────────────────────────────────────────────╯│
│ Do you want to make this edit?                                  │
│ ❯ 1. Yes                                                         │
│   2. No                                                          │
╰─────────────────────────────────────────────────────────────────╯
```

### Current Steve Code Style
- Shows full file contents by default
- XML action blocks (being hidden)
- Less visual hierarchy

## Key Differences

1. **Tool Format**: `● ToolName(args)` with bullet points
2. **Collapsible by Default**: Large outputs collapsed with line count
3. **Visual Hierarchy**: Clear separation between description and tool output
4. **Confirmation Prompts**: Interactive confirmations for destructive actions
5. **Progress Indicators**: Shows what's happening during operations

## Implementation in Steve Code

Steve Code already has:
- ✅ Collapsible sections (`CollapsibleSection` class)
- ✅ Response processing
- ✅ Rich console formatting
- ✅ Action detection and execution

What's needed:
- 🔧 Format tool invocations in Claude Code style
- 🔧 Default to collapsed for large outputs
- 🔧 Add the `⎿` connector for collapsed content
- 🔧 Enhance visual hierarchy

## Benefits

1. **Cleaner Output**: Less overwhelming for users
2. **Better UX**: Users can expand only what they need
3. **Faster Perception**: Quick overview of what AI is doing
4. **Professional Look**: Matches Claude Code's polished interface