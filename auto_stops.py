import sublime
import sublime_plugin
import threading
import uuid
import time
import sys
sys.path.append(sublime.packages_path() + "/User")  # Ensure the User folder is in the path
if sublime.packages_path():
    import myLib
else:
    def revive_this_plugin():
        def check():
            if sublime.packages_path():
                reload_this_plugin(this_plugin_name())
            else:
                sublime.set_timeout(check, 1000)  # Retry later
        check()
    revive_this_plugin()

SETTINGS = sublime.load_settings("AutoStops.sublime-settings")
IDLE_TIME = SETTINGS.get("idle_time", 2)           # seconds before we mark a stop
MAX_STOPMARKS = SETTINGS.get("max_stopmarks", 30)  # cap on auto-stops

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

def set_last_activity_snapshot(view, snapshot=None):
    if not snapshot:
        snapshot = view.substr(sublime.Region(0, view.size()))
    la_dict = next((d for d in AutoStopsListener.last_activity if d.get("view") == view), None)
    if la_dict:
        la_dict["snapshot"] = snapshot
    else:
        AutoStopsListener.last_activity.append({"view": view, "snapshot": snapshot})

def get_last_activity_snapshot(view):
    return next((d.get("snapshot", "") for d in AutoStopsListener.last_activity if d.get("view") == view), "")

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
        # Reset the activity timer whenever caret/selection changes
        set_last_activity_timestamp(view)

    def on_modified_async(self, view):
        with self.lock:
            # Push the activity timer far into future before updating the stops
            set_last_activity_timestamp(view, time.time() + 999)

            latest_snapshot = view.substr(sublime.Region(0, view.size()))
            recent_snapshot = get_last_activity_snapshot(view)
            # this checking brings short-circuit for the scenario "no recognized difference" (but why "no difference" can occur in on_modified? perhaps user typed too fast that the system failed to catch up (but that's okay, as the changes would just be accumulated in the upcoming on_modified events). some other scenarios may also cause this, such as, `undo` which seems to trigger on_modified one extra time.)
            if latest_snapshot == recent_snapshot:
                return
            rangeStart = myLib.find_diffpoint(recent_snapshot, latest_snapshot)
            endDepth = myLib.find_diffpoint(recent_snapshot, latest_snapshot, False)
            if rangeStart + endDepth > len(latest_snapshot) or rangeStart + endDepth > len(recent_snapshot):
                # adjust the result for a typical scenario when the immediate pre-text/post-text (of the modification) is identical
                # the known example of such scenario is "adding a new line between 2 existing lines" which will insert a newline character immediately after an existing newline character that these 2 consecutive newline characters could cause an overlap counting by 'the collaboration of "find_diffpoint forward" and "find_diffpoint backward"', hence the overlapping must be rectified.
                endDepth -= max((rangeStart + endDepth - len(latest_snapshot)), (rangeStart + endDepth - len(recent_snapshot)), 0)
            rangeEnd1 = len(latest_snapshot) - endDepth
            rangeEnd0 = len(recent_snapshot) - endDepth
            rangeLength = max(rangeEnd0, rangeEnd1) - rangeStart
            ecs_result = myLib.exclude_common_strings(recent_snapshot[rangeStart:rangeEnd0], latest_snapshot[rangeStart:rangeEnd1], 0, 0, 0, 0, False, int(rangeLength / 100000) + 3)
            if len(ecs_result) > 2:
                sublime.error_message("'exclude_common_strings' timeout")
                print(*ecs_result)
                return
            b4modi, afmodi = ecs_result[0], ecs_result[1]
            # for ecs without the "False" argument, check its results length against 0
            # if len(b4modi) == 0 == len(afmodi):  # this checking brings short-circuit for a typical scenario
            #     return
            # for ecs with the "False" argument, check its results length against 2 and compare their detail pair by pair
            # if len(b4modi) == 2 == len(afmodi):  # this block of codes tries to block a typical scenario
            #     all_the_same = True
            #     for i, region in enumerate(b4modi):
            #         if region[1] != region[0] or afmodi[i][1] != afmodi[i][0]:
            #             all_the_same = False
            #             break
            #     if all_the_same:  # skip it as it needs no process
            #         return
            if len(b4modi) != len(afmodi):
                sublime.error_message("unexpected scenario encountered: the total number of items in these", b4modi, afmodi, "lists are supposed equal but they are", len(b4modi), "and", len(afmodi), "respectively.")
            else:
                self.stops = view.settings().get("stops", [])
                n = max(len(recent_snapshot), len(latest_snapshot)) + 1
                for i, region in enumerate(b4modi):
                    net_change0 = min(afmodi[i][0], afmodi[i][1]) - min(region[0], region[1])
                    net_change1 = max(afmodi[i][0], afmodi[i][1]) - max(region[0], region[1])
                    if net_change0 or net_change1:
                        for stop in self.stops:
                            if min(region[0], region[1]) <= min(stop.get("region")[0], stop.get("region")[1]) - rangeStart < max(region[0], region[1]):
                                stop["region"][0] += net_change0
                                stop["region"][1] += net_change0
                            if max(region[0], region[1]) <= min(stop.get("region")[0], stop.get("region")[1]) - rangeStart < min((b4modi[i+1:]+[(n, n)])[0][0], (b4modi[i+1:]+[(n, n)])[0][1]):
                                stop["region"][0] += net_change1
                                stop["region"][1] += net_change1
                view.settings().set("stops", self.stops)
            set_last_activity_snapshot(view, latest_snapshot)

        # Reset the activity timer as buffer changes are handled
        set_last_activity_timestamp(view)

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
                self.stops = view.settings().get("stops", [])
                for region in sel:
                    if region_key(region) not in [stop["region"] for stop in self.stops]:
                        key = region_key(region)
                        self.stops.append({"region": key, "time": time.time()})
    
                # Enforce cap
                while len(self.stops) > MAX_STOPMARKS:
                    self.stops.pop(0)
    
                # Update stops in view settings
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

        # Preventive measure
        if IDLE_TIME == None or not sublime.packages_path():
            def revive_this_plugin():
                def check():
                    if sublime.packages_path():
                        reload_this_plugin(this_plugin_name())
                    else:
                        sublime.set_timeout(check, 1000)  # Retry later
                check()
            revive_this_plugin()

        snapshot = view.substr(sublime.Region(0, view.size()))
        if get_last_activity_snapshot(view) != snapshot:
            set_last_activity_snapshot(view, snapshot)

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
                return
            yesno = sublime.yes_no_cancel_dialog("[OK] to accept what is selected\n\n[Exclude] to take this one off the list\n\n[Cancel] to dismiss this dialog and stay with the panel", "OK", "Exclude")
            if yesno == sublime.DIALOG_YES:
                self.view.erase_regions("showScope")
                self.view.erase_regions("focusedRegion")
            elif yesno == sublime.DIALOG_NO:
                target = stops.pop(len(items)-i-1)["region"]
                self.view.settings().set("stops", stops)
                items.pop(i)
                self.view.window().show_quick_panel(items, on_done, 1, i if i < len(items) else len(items) - 1, on_highlight)
            else:
                self.view.window().show_quick_panel(items, on_done, 1, i, on_highlight)

        def on_highlight(i):
            r = sublime.Region(*stops[len(items)-i-1]["region"])
            self.view.sel().clear()
            self.view.sel().add(r)
            self.view.show_at_center(r)
            self.view.add_regions("focusedRegion", [r], "string", "dot")

        self.saved_selection = list(self.view.sel())
        self.view.add_regions("showScope", [sublime.Region(*stop.get("region")) for stop in stops], "string", "", sublime.DRAW_NO_FILL)
        self.view.window().show_quick_panel(items, on_done, 1, 0, on_highlight)
