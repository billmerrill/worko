#!/usr/bin/python3
# <xbar.title>Worko</xbar.title>
# <xbar.version>v0.1</xbar.version>
# <xbar.author>Bill Merrill</xbar.author>
# <xbar.author.github>billmerrill</xbar.author.github>
# <xbar.desc>Provide a scoreboard for work toward project goals</xbar.desc>
# <xbar.image>https://monkey.org/images/tmonkey.gif</xbar.image>
# <xbar.dependencies>python</xbar.dependencies>
# <xbar.abouturl>http://monkey.org/~bill/</xbar.abouturl>
# <swiftbar.hideAbout>true</swiftbar.hideAbout>
# <swiftbar.hideRunInTerminal>true</swiftbar.hideRunInTerminal>
# <swiftbar.hideLastUpdated>true</swiftbar.hideLastUpdated>
# <swiftbar.hideDisablePlugin>true</swiftbar.hideDisablePlugin>
# <swiftbar.hideSwiftBar>true</swiftbar.hideSwiftBar>

import csv
from collections import defaultdict
from copy import copy
from datetime import datetime, timedelta
import json
import os
import subprocess
import sys

# Configuration
WORKO_DATA_DIR = os.path.expanduser("~/.worko_data")
SESSION_JSON = os.path.join(WORKO_DATA_DIR, "current_session.json")
LOG_CSV = os.path.join(WORKO_DATA_DIR, "work_log.csv")
SUMMARY_CSV = os.path.join(WORKO_DATA_DIR, "projects_summary.csv")
SCOREBOARD_ROLLING_DAYS = 7
TOP_PROJECTS = 3


class WorkoLog:
    LOG_FIELDS = ["start_time", "end_time", "duration", "project", "results"]
    SUMMARY_FIELDS = ["project", "duration"]

    def __init__(self):
        self.filesystem_setup()
        self.load_summary()

    def filesystem_setup(self):
        if not os.path.exists(WORKO_DATA_DIR):
            os.makedirs(WORKO_DATA_DIR)
        elif not os.path.isdir(WORKO_DATA_DIR):
            raise ValueError(f"Path exists but is not a directory.")

    def get_top_projects(self):
        lim = min(TOP_PROJECTS, len(self.summary))
        return self.summary[:lim]

    def load_summary(self):
        self.summary = []
        try:
            with open(SUMMARY_CSV, "r") as fh:
                reader = csv.DictReader(fh, fieldnames=WorkoLog.SUMMARY_FIELDS)
                next(reader, None)  # skip header
                for row in reader:
                    row["duration"] = int(row["duration"])
                    self.summary.append(row)

        except (FileNotFoundError, json.JSONDecodeError):
            pass

    def save(self, session):
        self.write_entry(session)
        self.update_summary()

    def update_summary(self):
        # filter work log for the target rolling days
        project_durations = defaultdict(int)
        dt_now = datetime.now()
        dt_limit = timedelta(days=SCOREBOARD_ROLLING_DAYS)
        with open(LOG_CSV, "r") as fh:
            reader = csv.DictReader(fh, fieldnames=WorkoLog.LOG_FIELDS)
            next(reader, None)  # skip header
            for row in reader:
                dt_end = datetime.fromisoformat(row["end_time"])
                if dt_now - dt_end < dt_limit:
                    project_durations[row["project"]] += int(row["duration"])

        # new shape!
        tmp_summary = [
            {"project": pk, "duration": project_durations[pk]}
            for pk in project_durations
        ]
        tmp_summary.sort(key=lambda x: x["duration"], reverse=True)

        # write a new summary
        with open(SUMMARY_CSV, "w") as fh:
            writer = csv.DictWriter(fh, fieldnames=WorkoLog.SUMMARY_FIELDS)
            writer.writeheader()
            for proj in tmp_summary:
                writer.writerow(proj)

        self.summary = tmp_summary

    def write_entry(self, session):
        file_exists = os.path.isfile(LOG_CSV)
        with open(LOG_CSV, "a") as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=WorkoLog.LOG_FIELDS)

            if not file_exists:
                writer.writeheader()

            writer.writerow(
                {
                    "start_time": session["start_time"],
                    "end_time": session["end_time"],
                    "duration": session["duration"],
                    "project": session["project"],
                    "results": session["results"],
                }
            )


class WorkoSession:

    def __init__(self):
        self.load()

    def add_results(self, new_result):
        if self.is_active():
            self.data["active_session"]["results"] = (
                f"{self.data['active_session']['results']}\n{new_result}"
                if self.data["active_session"]["results"]
                else new_result
            )
            self.save()

    def cancel(self):
        self.data["active_session"] = None
        self.save()

    def end(self, results):
        s = self.data["active_session"]
        start_time = datetime.fromisoformat(s["start_time"])
        end_time = datetime.now()
        duration = end_time - start_time

        # Update session details
        s["end_time"] = end_time.isoformat()
        s["duration"] = str(round(duration.total_seconds()))
        s["results"] = results

        self.save()

        final_session = copy(self.data["active_session"])
        # Clear active session
        self.data["active_session"] = None
        self.save()
        return final_session

    def get(self):
        return self.data["active_session"]

    def get_results(self):
        if self.is_active():
            return self.data["active_session"]["results"]

    def is_active(self):
        return self.data["active_session"] is not None

    def load(self):
        try:
            with open(SESSION_JSON, "r") as f:
                self.data = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            self.data = {"active_session": None}

    def save(self):
        with open(SESSION_JSON, "w") as f:
            json.dump(self.data, f)

    def set_results(self, note):
        if self.is_active():
            self.data["active_session"]["results"] = note
            self.save()

    def start(self, project):
        self.data = {
            "active_session": {
                "start_time": datetime.now().isoformat(),
                "project": project,
                "end_time": None,
                "duration": None,
                "results": None,
            }
        }

        self.save()


class WorkoApp:
    def __init__(self):
        self.session = WorkoSession()
        self.log = WorkoLog()

    def add_note(self):
        if not self.session.is_active():
            return

        # Prompt for results
        new_note = self.prompt_user("Add a session note.")
        if new_note is False:
            return  # cancel
        self.session.add_results(new_note)

    @staticmethod
    def display_duration(seconds):
        seconds = int(seconds)
        v = []
        if (seconds // 3600) > 0:
            v.append(f"{seconds//3600}h")
        if seconds % 3600:
            v.append(f"{(seconds % 3600) // 60}m")

        return " ".join(v)

    def display_menu(self):
        active_session = self.session.get()

        if self.session.is_active():
            start_time = datetime.fromisoformat(active_session["start_time"])
            duration = datetime.now() - start_time
            duration = WorkoApp.display_duration(duration.total_seconds())

            print(f"Ⓦ **{active_session['project']}** |  md=True")
            print("---")
            print(
                f"Add Note | refresh=True bash='{sys.argv[0]}' param1=note terminal=false"
            )
            print(
                f"End Session | shortcut=CMD+CTRL+L refresh=True bash='{sys.argv[0]}' param1=toggle terminal=false"
            )
            print("---")
            print("Current Session")
            print(f"Project: {active_session['project']}")
            print(f"Duration: {duration}")
            print("---")
            print(
                f"Cancel Session | shortcut=CMD+CTRL+L refresh=True bash='{sys.argv[0]}' param1=cancel terminal=false"
            )

        else:
            print("ⓦ | md=True")
            print("---")
            print(
                f"Start New Session | shortcut=CMD+CTRL+L refresh=True bash='{sys.argv[0]}' param1=toggle terminal=false"
            )

            top_projects = self.log.get_top_projects()
            if len(top_projects) > 0:
                print("---")
                print("Top Projects")
            for tp in top_projects:
                print(
                    f"Start {tp['project']} ({WorkoApp.display_duration(tp['duration'])}) | refresh=True bash='{sys.argv[0]}' param1='{tp['project']}' terminal=false"
                )

        print("---")
        print(
            f"Open data directory | refresh=True bash='{sys.argv[0]}' param1='opendata' terminal=false"
        )
        print("ⓦ Worko oh yeah!")

    def end_session(self):
        # Check if there's an active session
        if not self.session.is_active():
            return

        # Prompt for results
        current_results = self.session.get_results()
        results = self.prompt_user(
            "What did you accomplish in this work session?",
            f"{current_results}\n" if current_results else "\n\n",
        )

        if results is False:
            return  # cancel

        if not results:
            results = ""

        # Retrieve and complete the session
        session_data = self.session.end(results)
        self.log.save(session_data)

    def cancel_session(self):
        if not self.session.is_active():
            return

        self.session.cancel()

    def prompt_user(self, message, answer=""):
        """Use AppleScript to show a dialog and return user input"""
        script = f'display dialog "{message}" default answer "{answer}"'
        try:
            result = subprocess.check_output(
                ["osascript", "-e", script], universal_newlines=True
            )
            # Extract the text after "text returned:"
            return result.split(":")[-1].strip()

        # hit cancel
        except subprocess.CalledProcessError as e:
            return False

    def start_session(self, project=""):
        # Prompt for project using AppleScript
        project = self.prompt_user("Project tag", project)

        if project is False:
            return  # cancel

        if not project:
            project = "freeform"

        self.session.start(project)

    def toggle_session(self):
        if self.session.is_active():
            self.end_session()
        else:
            self.start_session()


def main():
    tracker = WorkoApp()
    if len(sys.argv) > 1:
        if sys.argv[1] == "note":
            tracker.add_note()
        elif sys.argv[1] == "toggle":
            tracker.toggle_session()
        elif sys.argv[1] == "cancel":
            tracker.cancel_session()
        elif sys.argv[1] == "opendata":
            subprocess.run(["/usr/bin/open", WORKO_DATA_DIR])
        else:
            tracker.start_session(sys.argv[1])
    else:
        tracker.display_menu()


if __name__ == "__main__":
    main()
