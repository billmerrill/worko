#!/usr/bin/python3

import csv
from collections import defaultdict
from datetime import datetime, timedelta
import json
import os
import subprocess
import sys

# Configuration
WORKO_DATA_DIR = os.path.expanduser('~/.worko_data')
SESSION_JSON = os.path.join(WORKO_DATA_DIR, 'current_session.json')
LOG_CSV = os.path.join(WORKO_DATA_DIR, 'work_sessions.csv')
SUMMARY_CSV = os.path.join(WORKO_DATA_DIR, 'project_summary.csv')
SCOREBOARD_ROLLING_DAYS = 7
TOP_PROJECTS = 3

class WorkoData:
    LOG_FIELDS = ['start_time', 'end_time', 'duration', 'project', 'results']
    SUMMARY_FIELDS = ['project', 'duration']

    def __init__(self):
        self.filesystem_setup()
        self.load_summary()

    def get_top_projects(self):
        lim = min(TOP_PROJECTS, len(self.summary))
        return self.summary[:lim]

    def filesystem_setup(self):
        if not os.path.exists(WORKO_DATA_DIR):
            os.makedirs(WORKO_DATA_DIR)
        elif not os.path.isdir(WORKO_DATA_DIR):
            raise ValueError(f"Path exists but is not a directory.")

    def save_session(self, session):
        self.write_log(session)
        self.update_summary()

    def load_summary(self):
        self.summary = []
        try:
            with open(SUMMARY_CSV, 'r') as fh:
                reader = csv.DictReader(fh, fieldnames=WorkoData.SUMMARY_FIELDS)
                for row in reader:
                    self.summary.append(row)
        except (FileNotFoundError, json.JSONDecodeError):
            pass

    def update_summary(self):

        # filter work log for the target rolling days
        project_durations = defaultdict(int)
        dt_now =  datetime.now()
        dt_limit = timedelta(days=SCOREBOARD_ROLLING_DAYS)
        with open(LOG_CSV, 'r') as fh:
            reader = csv.DictReader(fh, fieldnames=WorkoData.LOG_FIELDS)
            for row in reader:
                print("OHAHI", row)
                dt_end = datetime.fromisoformat(row['end_time'])
                if dt_now - dt_end < dt_limit:
                    project_durations[row['project']] += int(row['duration'])

        tmp_summary = [{'project': pk, 'duration': project_durations[pk]} for pk in project_durations]
        tmp_summary.sort(key=lambda x: x['duration'], reverse=True)

        # write a new summary 
        with open(SUMMARY_CSV, 'w') as fh:
            writer = csv.DictWriter(fh, fieldnames=WorkoData.SUMMARY_FIELDS)
            writer.writeheader()
            for proj in tmp_summary:
                writer.writerow(proj)
        
        self.summary = tmp_summary

    
    def write_log(self, session):
        file_exists = os.path.isfile(LOG_CSV)
        with open(LOG_CSV, 'a') as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=WorkoData.LOG_FIELDS)
            
            if not file_exists:
                writer.writeheader()
            
            writer.writerow({
                'start_time': session['start_time'],
                'end_time': session['end_time'],
                'duration': session['duration'],
                'project': session['project'],
                'results': session['results']
            })
 
class WorkoApp:
    def __init__(self):
        self.session = self.load_session()
        self.data = WorkoData()
    
    def load_session(self):
        try:
            with open(SESSION_JSON, 'r') as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            return {'active_session': None}
    
    def save_session(self):
        with open(SESSION_JSON, 'w') as f:
            json.dump(self.session, f)
    
    def prompt_user(self, message, answer=""):
        """Use AppleScript to show a dialog and return user input"""
        script = f'display dialog "{message}" default answer "{answer}"'
        try:
            result = subprocess.check_output(['osascript', '-e', script], 
                                             universal_newlines=True)
            # Extract the text after "text returned:"
            return result.split(':')[-1].strip()
        except subprocess.CalledProcessError:
            return None
    
    def start_session(self):
        # Prompt for project using AppleScript
        project = self.prompt_user("Project tag:")
        
        if not project:
            project = "freeform"
        
        # Create session record
        session = {
            'start_time': datetime.now().isoformat(),
            'project': project,
            'end_time': None,
            'duration': None,
            'results': None
        }
        
        # Save session to config
        self.session['active_session'] = session
        self.save_session()
        
    
    def end_session(self):
        # Check if there's an active session
        if not self.session['active_session']:
            self.prompt_user("No active work session to end.")
            return
        
        # Prompt for results
        results = self.prompt_user("What did you accomplish in this work session?", "\n\n")
        
        if not results:
            results = "Untracked session"
        
        # Retrieve and complete the session
        session = self.session['active_session']
        start_time = datetime.fromisoformat(session['start_time'])
        end_time = datetime.now()
        duration = end_time - start_time
        
        # Update session details
        session['end_time'] = end_time.isoformat()
        session['duration'] = str(round(duration.total_seconds()))
        session['results'] = results
        
        self.data.save_session(session)
        
        # Clear active session
        self.session['active_session'] = None
        self.save_session()
    
    def toggle_session(self):
        if self.session['active_session']:
            self.end_session()
        else:
            self.start_session()
    
   
    def display_menu(self):
        active_session = self.session.get('active_session')
        
        if active_session:
            # Working session is active
            start_time = datetime.fromisoformat(active_session['start_time'])
            duration = datetime.now() - start_time
            
            # Menu bar display when session is active
            print(f"㏒: **{active_session['project']}** |  md=True")
            print("---")
            print("End Session | shortcut=CMD+CTRL+L refresh=True bash='{}' param1=end terminal=false".format(sys.argv[0]))
            print(f"Focus: {active_session['project']}")
            print(f"Duration: {duration}")
        else:
            # No active session
            print("㏒ | md=True")
            print("---")
            print("Start New Session | shortcut=CMD+CTRL+L refresh=True bash='{}' param1=start terminal=false".format(sys.argv[0]))
            top_projects = self.data.get_top_projects()
            for tp in top_projects:
                print(f"{tp['project']}: {round(tp['duration'] / 3600.0, 3)} hrs")

def main():
    tracker = WorkoApp()
    if len(sys.argv) > 1:
        tracker.toggle_session()
    tracker.display_menu()

if __name__ == '__main__':
    main()
