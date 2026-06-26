# SuperScheduler

SuperScheduler is a small wxPython desktop scheduling app with a one-week calendar view, a task side panel, local JSON persistence, and optional Google Calendar sync.

## Features

- Week-at-a-glance schedule with hour rows and seven day columns.
- Double-click the schedule grid to create an event in that time slot.
- Double-click an existing event to edit its title, date, time, and notes.
- Drag events to move them, or drag their top/bottom edges to resize their times.
- Right-click an event to edit, create another event, or delete it.
- Task side panel with add, complete, delete, and left/right placement controls.
- Local events and tasks are saved to `superscheduler_data.json`.
- Google Calendar OAuth connection can import events from your primary calendar.
- New events can be saved locally or sent to Google Calendar after connecting.

## Setup

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python app.py
```

## Google Calendar Setup

1. Create or choose a project in Google Cloud Console.
2. Enable the Google Calendar API for that project.
3. Configure an OAuth consent screen.
4. Create OAuth credentials for a Desktop app.
5. Download the OAuth client JSON file and rename it to `credentials.json`.
6. Place `credentials.json` in this folder beside `app.py`.
7. Run `python app.py`, then click `Connect Google`.

After the first successful sign-in, the app stores `token.json` beside `app.py` so you do not need to log in every time.

## Notes

- The app uses your primary Google Calendar.
- Local events remain local unless you check `Add to Google Calendar` in the event dialog.
- Google events are loaded for the visible week when you connect or sync.
