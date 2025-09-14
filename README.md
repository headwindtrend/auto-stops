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
  Configure idle timeout, and maximum stored stops.

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
    "max_stopmarks": 30
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

Create or edit `myLib.py`

1. copy & paste this `def` (as shown below) into `myLib.py`.
```python
def find_diffpoint(a: str, b: str, forward=True, threshold: int = 0) -> int:
	"""
	Find the index at which two strings first differ or the index from the end where two strings start to differ.
	Uses a linear scan for small strings and binary search for large ones.

	:param a: First string
	:param b: Second string
	:param forward: True for forward mode, False for backward mode
	:param threshold: Switch to binary search when both strings are longer than this
	:return: Number of matching characters from the beginning or from the end (depends on the argument 'forward'), or return -1 if identical
	"""
	if a == b:
		return -1

	len_a, len_b = len(a), len(b)
	max_len = min(len_a, len_b)
	if forward:
		if a[:max_len] == b[:max_len]:
			return max_len
	else:
		if a[-max_len:] == b[-max_len:]:
			return max_len

	if max_len < threshold:
		# Linear comparison for small inputs
		if forward:
			for i in range(max_len):
				if a[i] != b[i]:
					return i
		else:
			for i in range(1, max_len + 1):
				if a[-i] != b[-i]:
					return i - 1
		return 0
	else:
		# Binary search for large inputs
		low, high = 0, max_len
		mid = (low + high) // 2
		while low < mid:
			no_diff = False
			if forward:
				if a[low:mid] == b[low:mid]:
					no_diff = True
			else:
				if a[len_a-mid:len_a-low] == b[len_b-mid:len_b-low]:
					no_diff = True
			if no_diff:
				low = mid
			else:
				high = mid
			mid = (low + high) // 2
		return low
```
2. also copy & paste the entire ecs (the `exclude_common_strings()` and a few other `def` that it will use as well as the relevant `import` statements) from [fast-diffing](https://github.com/headwindtrend/fast-diffing/blob/main/diffing.py) into `myLib.py`.

---

# If you appreciate my work, i will be very grateful if you can support my work by making small sum donation thru PayPal with `Send payment to` entered as `headwindtrend@gmail.com`. Thank you very much for your support.
