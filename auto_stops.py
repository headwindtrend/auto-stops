import sublime
import sublime_plugin
import threading
import time

SETTINGS = sublime.load_settings("AutoStops.sublime-settings")
IDLE_TIME = SETTINGS.get("idle_time", 2)           # seconds before we mark a stop
MAX_STOPMARKS = SETTINGS.get("max_stopmarks", 30)  # cap on auto-stops
CONTEXT_LEN = SETTINGS.get("context_len", 10)      # how many characters before and after the stop would be kept as the context_sense

import os
def this_plugin_name():
    return os.path.join(sublime.packages_path(), "User", "auto_stops.py")

def reload_this_plugin(file_name, view=sublime.active_window().active_view()):
    plugin_view = None
    for window in sublime.windows():
        plugin_view = window.find_open_file(file_name)
        if plugin_view:
            # plugin_window = window
            break
    if plugin_view:
        plugin_view.run_command('save')
    else:
        def finishes_the_save_after_open():
            sublime.active_window().focus_view(view)
            plugin_view.run_command('save')
        try:
            plugin_view = sublime.active_window().open_file(file_name)
        except:
            sublime.error_message('"' + file_name + '" failed to open.')
            return
        sublime.set_timeout(lambda: finishes_the_save_after_open(), 1000)


def pre_text(view, region):
    context_sense = (region.begin() - CONTEXT_LEN, region.begin())
    return repr(view.substr(sublime.Region(*context_sense)))

def post_text(view, region):
    context_sense = (region.end(), region.end() + CONTEXT_LEN)
    return repr(view.substr(sublime.Region(*context_sense)))

def region_key(region):
    """Serialize a Region to a tuple so we can compare and track them."""
    return [region.a, region.b]

def set_last_activity_timestamp(view, timestamp=time.time()):
    la_dict = next((d for d in AutoStopsListener.last_activity if d.get("view") == view), None)
    if la_dict:
        la_dict["timestamp"] = timestamp
    else:
        AutoStopsListener.last_activity.append({"view": view, "timestamp": timestamp})

def get_last_activity_timestamp(view):
    return next((d.get("timestamp") for d in AutoStopsListener.last_activity if d.get("view") == view), None)

def set_periodic_token(view, token=str(uuid.uuid4())):
    la_dict = next((d for d in AutoStopsListener.last_activity if d.get("view") == view), None)
    if la_dict:
        la_dict["token"] = token
    else:
        AutoStopsListener.last_activity.append({"view": view, "token": token})

def get_periodic_token(view):
    return next((d.get("token", "") for d in AutoStopsListener.last_activity if d.get("view") == view), "")


class AutoStopsListener(sublime_plugin.EventListener):
    lock = threading.Lock()
    last_activity = []  # list of dicts: {"view": view, "timestamp": float}
    stops = []  # list of dicts: {"region": [a, b], "time": float}

    def on_selection_modified_async(self, view):
        if not view or not view.window() or view != view.window().active_view():
            return
        # Reset the activity timer whenever caret/selection changes
        set_last_activity_timestamp(view)

    def on_modified_async(self, view):
        if not view or not view.window() or view != view.window().active_view():
            return
        # also reset timer if buffer changes
        set_last_activity_timestamp(view)

        with self.lock:
            # Update stops in view settings from stopmarks which are supposed been automatically adjusted by sublime accordingly for the eventual modification that might have impacted the exact positions of some (if not all) of the stopmarks
            stopmarks = view.get_regions("stopmarks")
            if stopmarks:
                self.stops = view.settings().get("stops", [])
                for index, region in enumerate(stopmarks):
                    key = region_key(region)
                    matched = next((stop for stop in self.stops if stop.get("region") == key and stop.get("pre_str") == pre_text(view, region) and stop.get("post_str") == post_text(view, region)), None)
                    if matched:
                        if matched["marks_index"] != index:
                            matched["marks_index"] = index
                    else:
                        matched = next((stop for stop in self.stops if stop.get("region") and abs(stop.get("region")[1] - stop.get("region")[0]) == region.end() - region.begin() and stop.get("pre_str") == pre_text(view, region) and stop.get("post_str") == post_text(view, region)), None)
                        if matched:
                            matched["region"] = key
                            matched["marks_index"] = index
                        else:
                            matched = next((stop for stop in self.stops if stop.get("marks_index") == index and stop.get("pre_str") == pre_text(view, region) and stop.get("post_str") == post_text(view, region)), None)
                            if matched:
                                matched["region"] = key
                            else:
                                matched = next((stop for stop in self.stops if stop.get("region") == key and stop.get("marks_index") == index), None)
                                if matched:
                                    matched["pre_str"] = pre_text(view, region)
                                    matched["post_str"] = post_text(view, region)
                                else:
                                    matched = next((stop for stop in self.stops if stop.get("region") and abs(stop.get("region")[1] - stop.get("region")[0]) == region.end() - region.begin() and stop.get("post_str") == post_text(view, region)), None)
                                    if matched:
                                        matched["region"] = key
                                        matched["marks_index"] = index
                                        matched["pre_str"] = pre_text(view, region)
                                    else:
                                        self.stops.append({"region": key, "marks_index": index, "pre_str": pre_text(view, region), "post_str": post_text(view, region), "time": time.time()})
                view.settings().set("stops", self.stops)

    def on_pre_close(self, view):
        AutoStopsListener.last_activity = [d for d in AutoStopsListener.last_activity if d.get("view") != view]

    def check_idle(self, view):
        if not self.lock.acquire(blocking=False):  # don’t wait
            # Someone else (on_modified) is running, so skip quietly
            return

        try:
            """Check if caret stayed idle long enough; if so, record a stop."""
            now = time.time()
            last_activity = get_last_activity_timestamp(view)
            if last_activity and (now - last_activity) >= IDLE_TIME:
                sel = list(view.sel())
                if not sel:
                    return
                if sel[0].begin() == view.settings().get("skip_auto_stops") == sel[0].end():
                    view.settings().erase("skip_auto_stops")
                    return
                stopmarks = view.get_regions("stopmarks")
                self.stops = view.settings().get("stops", [])
                for region in sel:
                    if region_key(region) not in [stop["region"] for stop in self.stops]:
                        key = region_key(region)
    
                        # Add stopmark
                        stopmarks.append(region)
    
                        # Track in side list
                        self.stops.append({"region": key, "marks_index": None, "pre_str": pre_text(view, region), "post_str": post_text(view, region), "time": time.time()})
    
                # Enforce cap
                while len(self.stops) > MAX_STOPMARKS:
                    oldest = self.stops.pop(0)["region"]
                    stopmarks = [r for r in stopmarks if region_key(r) != oldest]
    
                # Update "regions" in Sublime
                view.add_regions("stopmarks", stopmarks)
    
                # Update stops in view settings
                stopmarks = view.get_regions("stopmarks")
                for index, region in enumerate(stopmarks):
                    key = region_key(region)
                    matched = next((stop for stop in self.stops if stop.get("region") == key), None)
                    if matched:
                        matched["marks_index"] = index
                view.settings().set("stops", self.stops)
    
                # reset timer so we don’t immediately add again
                set_last_activity_timestamp(view, now + 999)  # push far into future

        finally:
            self.lock.release()

    def on_activated_async(self, view):
        if not view or not view.window() or view != view.window().active_view():
            return
        # Reset the activity timer when the view is activated
        set_last_activity_timestamp(view)

        # Get stops of this view
        self.stops = view.settings().get("stops", [])
        # Update stopmarks
        view.erase_regions("stopmarks")
        stopmarks = []
        if self.stops and len(self.stops):
            for stop in self.stops:
                stopmarks.append(sublime.Region(*stop["region"]))
        if stopmarks and len(stopmarks):
            view.add_regions("stopmarks", stopmarks)

        # Preventive measure
        if IDLE_TIME == None:
            def revive_this_plugin():
                def check():
                    if sublime.packages_path():
                        reload_this_plugin(this_plugin_name())
                    else:
                        sublime.set_timeout(check, 1000)  # Retry later
                check()
            revive_this_plugin()

        # Run periodic idle checks
        set_periodic_token(view)
        sublime.set_timeout_async(lambda: self.periodic(view, get_periodic_token(view)), 1000)

    def periodic(self, view, token):
        # Called every 1s when view is active
        if token != get_periodic_token(view) or view.window() is None or view != view.window().active_view():
            return  # view closed or not in focus
        self.check_idle(view)
        sublime.set_timeout_async(lambda: self.periodic(view, token), 1000)


class ClearAutoStopsCommand(sublime_plugin.TextCommand):
    def run(self, edit, **kwargs):
        self.view.settings().erase("stops")
        self.view.erase_regions("stopmarks")
        sublime.status_message("Erased all auto-stops records.")

class ShowAutoStopsCommand(sublime_plugin.TextCommand):
    def run(self, edit, **kwargs):
        stops = self.view.settings().get("stops", [])
        if not stops:
            sublime.status_message("No auto-stops recorded yet.")
            return

        items = []
        for s in stops:
            r = sublime.Region(*s["region"])
            line_region = self.view.line(r)
            text = self.view.substr(line_region).strip()
            if not text:
                text = "<blank line>"
            timestamp = s["time"]
            if timestamp:
                delta = time.time() - timestamp
                if delta < 0:
                    delta = 0
                h, remainder = divmod(int(delta), 3600)
                m, s = divmod(remainder, 60)
                d = int((delta % 1) * 100)
                timestamp_str = f"{h}:{m:02d}:{s:02d}.{d:02d} ago"
            else:
                timestamp_str = "{unknown} ago"
            items.insert(0, timestamp_str.rjust(16) + (" — " + str(r)).ljust(17) + (" line " + str(self.view.rowcol(r.begin())[0] + 1)).ljust(10) + " — " + text)

        def on_done(i):
            if i == -1:
                self.view.erase_regions("showScope")
                self.view.erase_regions("focusedRegion")
                self.view.sel().clear()
                self.view.sel().add_all(self.saved_selection)
                self.view.hide_popup()
                return
            yesno = sublime.yes_no_cancel_dialog("[OK] to accept what is selected\n\n[Exclude] to take this one off the list\n\n[Cancel] to dismiss this dialog and stay with the panel", "OK", "Exclude")
            if yesno == sublime.DIALOG_YES:
                self.view.erase_regions("showScope")
                self.view.erase_regions("focusedRegion")
                self.view.sel().clear()
                self.view.sel().add(sublime.Region(*stops[len(items)-i-1]["region"]))
            elif yesno == sublime.DIALOG_NO:
                target = stops.pop(len(items)-i-1)["region"]
                self.view.settings().set("stops", stops)
                items.pop(i)
                self.view.add_regions("stopmarks", [r for r in self.view.get_regions("stopmarks") if region_key(r) != target])
                self.view.window().show_quick_panel(items, on_done, 1, i if i < len(items) else len(items) - 1, on_highlight)
            else:
                self.view.window().show_quick_panel(items, on_done, 1, i, on_highlight)

        def on_highlight(i):
            r = sublime.Region(*stops[len(items)-i-1]["region"])
            self.view.sel().clear()
            self.view.settings().set("skip_auto_stops", r.begin())
            self.view.sel().add(r.begin())
            self.view.show_at_center(r)
            self.view.add_regions("focusedRegion", [r], "string", "dot")
            self.view.hide_popup()
            if r.end() == r.begin():
                self.view.show_popup("<div style='font-size:12;background-color:yellow;color:black'>↑ Text Cursor")

        self.saved_selection = list(self.view.sel())
        self.view.add_regions("showScope", [sublime.Region(*stop.get("region")) for stop in stops], "string", "", sublime.DRAW_NO_FILL)
        self.view.window().show_quick_panel(items, on_done, 1, 0, on_highlight)
