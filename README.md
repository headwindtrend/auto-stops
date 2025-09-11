# auto-stops
**AutoStops** is a Sublime Text 3 plugin that automatically remembers "stops" —   points where your cursor (or selection) stayed idle for a few seconds.   It’s like having automatic, time-aware bookmarks that you can quickly jump back to.

---

## Features

- ⏱ **Automatic stopmarks**  
  Records your selection after `idle_time` seconds of inactivity.

- 📌 **Persistent memory**  
  Stops are saved with the view and restored when you reopen the file.

- 🧭 **Quick navigation**  
  Open a panel with all stops, preview by highlighting, and jump back instantly.

- 🧹 **Cleanup controls**  
  Clear all stops in the current view with a single command.

- ⚙️ **Customizable**  
  Configure idle timeout, maximum stored stops, and context size.

---

## Commands

These commands are available in the Command Palette:

- **AutoStops: Show Stops**  
  Opens a quick panel with your recent stops.  
  - Arrow keys (or Rightclick) to preview.
  - `Enter` (or Click) to jump or remove.
    - `OK` → jump to the selected stop.  
    - `Exclude` → remove the selected stop.  
  - `Esc` → close and restore selection.

- **AutoStops: Clear Stops**  
  Erases all stored stops for the current view.

---

## Settings

Create or edit `AutoStops.sublime-settings`:

```json
{
    // Seconds of inactivity before recording a stop
    "idle_time": 2,

    // Maximum number of stops to keep (oldest are discarded)
    "max_stopmarks": 30,

    // Number of context characters to store before/after stop
    "context_len": 10
}
```

---

## Setup

Create or edit `Default.sublime-commands`

```json
[
    { "caption": "AutoStops: Show Stops", "command": "show_auto_stops" },
    { "caption": "AutoStops: Clear Stops", "command": "clear_auto_stops" }
]
```

Create or edit `Default (Windows).sublime-keymap`

```json
[
	{ "keys": ["ctrl+alt+f2"], "command": "show_auto_stops" },
	{ "keys": ["ctrl+alt+shift+f2"], "command": "clear_auto_stops" },
]
```

---

# If you appreciate my work, i will be very grateful if you can support my work by making small sum donation thru PayPal with `Send payment to` entered as `headwindtrend@gmail.com`. Thank you very much for your support.
