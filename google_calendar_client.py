from datetime import date, datetime, time, timedelta
from pathlib import Path
import uuid

from time_management import local_tz, parse_datetime
from schedule_event import ScheduleEvent

GOOGLE_SCOPES = ["https://www.googleapis.com/auth/calendar.events"]

class GoogleCalendarClient:
    def __init__(self, credentials_path: Path, token_path: Path):
        self.credentials_path = credentials_path
        self.token_path = token_path
        self.service = None

    def connect(self):
        try:
            from google.auth.transport.requests import Request
            from google.oauth2.credentials import Credentials
            from google_auth_oauthlib.flow import InstalledAppFlow
            from googleapiclient.discovery import build
        except ImportError as exc:
            raise RuntimeError(
                "Google Calendar packages are not installed. Run: pip install -r requirements.txt"
            ) from exc

        credentials = None
        if self.token_path.exists():
            credentials = Credentials.from_authorized_user_file(str(self.token_path), GOOGLE_SCOPES)

        if not credentials or not credentials.valid:
            if credentials and credentials.expired and credentials.refresh_token:
                credentials.refresh(Request())
            else:
                if not self.credentials_path.exists():
                    raise RuntimeError(
                        "Missing credentials.json. Create a Google OAuth desktop client and place "
                        "the downloaded file next to app.py."
                    )
                flow = InstalledAppFlow.from_client_secrets_file(str(self.credentials_path), GOOGLE_SCOPES)
                credentials = flow.run_local_server(port=0)

            self.token_path.write_text(credentials.to_json(), encoding="utf-8")

        self.service = build("calendar", "v3", credentials=credentials)
        return self.service

    def is_connected(self) -> bool:
        return self.service is not None

    def list_events(self, week_start: date) -> list[ScheduleEvent]:
        service = self.service or self.connect()
        start_dt = datetime.combine(week_start, time.min).replace(tzinfo=local_tz())
        end_dt = start_dt + timedelta(days=7)

        result = (
            service.events()
            .list(
                calendarId="primary",
                timeMin=start_dt.isoformat(),
                timeMax=end_dt.isoformat(),
                singleEvents=True,
                orderBy="startTime",
            )
            .execute()
        )

        events = []
        for item in result.get("items", []):
            start_payload = item.get("start", {})
            end_payload = item.get("end", {})
            raw_start = start_payload.get("dateTime") or start_payload.get("date")
            raw_end = end_payload.get("dateTime") or end_payload.get("date")
            if not raw_start or not raw_end:
                continue

            start_value = self._parse_google_time(raw_start)
            end_value = self._parse_google_time(raw_end)
            events.append(
                ScheduleEvent(
                    event_id=item.get("id", str(uuid.uuid4())),
                    title=item.get("summary", "Untitled"),
                    start=start_value,
                    end=end_value,
                    source="google",
                    description=item.get("description", ""),
                )
            )
        return events

    def create_event(self, event: ScheduleEvent) -> ScheduleEvent:
        service = self.service or self.connect()
        body = {
            "summary": event.title,
            "description": event.description,
            "start": {"dateTime": event.start.isoformat()},
            "end": {"dateTime": event.end.isoformat()},
        }
        created = service.events().insert(calendarId="primary", body=body).execute()
        event.event_id = created.get("id", event.event_id)
        event.source = "google"
        return event

    def update_event(self, event: ScheduleEvent) -> ScheduleEvent:
        service = self.service or self.connect()
        body = {
            "summary": event.title,
            "description": event.description,
            "start": {"dateTime": event.start.isoformat()},
            "end": {"dateTime": event.end.isoformat()},
        }
        updated = (
            service.events()
            .update(calendarId="primary", eventId=event.event_id, body=body)
            .execute()
        )
        event.event_id = updated.get("id", event.event_id)
        event.source = "google"
        return event

    def delete_event(self, event: ScheduleEvent) -> None:
        service = self.service or self.connect()
        service.events().delete(calendarId="primary", eventId=event.event_id).execute()

    @staticmethod
    def _parse_google_time(raw_value: str) -> datetime:
        if "T" not in raw_value:
            parsed_date = date.fromisoformat(raw_value)
            return datetime.combine(parsed_date, time.min).replace(tzinfo=local_tz())
        return parse_datetime(raw_value.replace("Z", "+00:00")).astimezone(local_tz())
