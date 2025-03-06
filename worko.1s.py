#!/usr/bin/python3

import os
import sys
import csv
from datetime import datetime, timedelta
import json
import subprocess

# Configuration
WORKO_DATA_DIR = os.path.expanduser('~/.worko_data')
CONFIG_JSON = os.path.join(WORKO_DATA_DIR, 'config.json')
LOG_CSV = os.path.join(WORKO_DATA_DIR, 'tmp_work_sessions.csv')
SUMMARY_CSV = os.path.join(WORKO_DATA_DIR, 'project_summary.csv')
SCOREBOARD_ROLLING_DAYS = 7

class WorkTracker:
    def __init__(self):
        self.config = self.load_config()
    
    def load_config(self):
        try:
            with open(CONFIG_JSON, 'r') as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            return {'active_session': None}
    
    def save_config(self):
        with open(CONFIG_JSON, 'w') as f:
            json.dump(self.config, f)
    
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
        project = self.prompt_user("Tag for work to be done:")
        
        if not project:
            project = "open-session"
        
        # Create session record
        session = {
            'start_time': datetime.now().isoformat(),
            'project': project,
            'end_time': None,
            'duration': None,
            'results': None
        }
        
        # Save session to config
        self.config['active_session'] = session
        self.save_config()
        
    
    def end_session(self):
        # Check if there's an active session
        if not self.config['active_session']:
            self.prompt_user("No active work session to end.")
            return
        
        # Prompt for results
        results = self.prompt_user("What did you accomplish in this work session?", "\n\n")
        
        if not results:
            results = "Untracked session"
        
        # Retrieve and complete the session
        session = self.config['active_session']
        start_time = datetime.fromisoformat(session['start_time'])
        end_time = datetime.now()
        duration = end_time - start_time
        
        # Update session details
        session['end_time'] = end_time.isoformat()
        session['duration'] = str(duration)
        session['results'] = results
        
        # Save to CSV
        self.save_to_csv(session)
        
        # Clear active session
        self.config['active_session'] = None
        self.save_config()
        
        
        # Notify user
        # self.prompt_user("Work session ended and saved!")
    
    def toggle_session(self):
        if self.config['active_session']:
            self.end_session()
        else:
            self.start_session()
    
    def save_to_csv(self, session):
        # Ensure CSV file exists with headers
        file_exists = os.path.isfile(CSV_FILE)
        with open(CSV_FILE, 'a', newline='') as csvfile:
            fieldnames = ['start_time', 'end_time', 'duration', 'project', 'results']
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            
            if not file_exists:
                writer.writeheader()
            
            writer.writerow({
                'start_time': session['start_time'],
                'end_time': session['end_time'],
                'duration': session['duration'],
                'project': session['project'],
                'results': session['results']
            })
    
    def display_menu(self):
        active_session = self.config.get('active_session')
        
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

def main():
    tracker = WorkTracker()
    if len(sys.argv) > 1:
        tracker.toggle_session()
    tracker.display_menu()

if __name__ == '__main__':
    main()
