from __future__ import annotations

import base64
import json
from pathlib import Path
from typing import Any

from settings import Settings

FEEDBACK_COLUMNS = ["Query", "Response", "Like/Dislike"]
FEEDBACK_LABELS = {
    "like": "Like",
    "thumbs_up": "Like",
    "up": "Like",
    "dislike": "Dislike",
    "thumbs_down": "Dislike",
    "down": "Dislike",
}


def normalize_feedback(value: Any) -> str:
    label = FEEDBACK_LABELS.get(str(value or "").strip().lower())
    if not label:
        raise ValueError("Feedback must be Like or Dislike.")
    return label


class FeedbackLogger:
    def __init__(self, settings: Settings):
        self.settings = settings
        self._worksheet: Any | None = None

    def append(self, query: str, response: str, feedback: str) -> None:
        query = query.strip()
        response = response.strip()
        feedback = normalize_feedback(feedback)
        if not query:
            raise ValueError("Query is required.")
        if not response:
            raise ValueError("Response is required.")

        if self.settings.feedback_apps_script_url.strip():
            self._append_to_apps_script(query, response, feedback)
            return

        worksheet = self._get_worksheet()
        worksheet.append_row(
            [query, response, feedback],
            value_input_option="USER_ENTERED",
        )

    def _append_to_apps_script(self, query: str, response: str, feedback: str) -> None:
        try:
            import requests
        except ImportError as exc:
            raise RuntimeError(
                "requests is not installed. Run pip install -r requirements.txt."
            ) from exc

        payload = {
            "query": query,
            "response": response,
            "feedback": feedback,
        }
        if self.settings.feedback_apps_script_secret:
            payload["secret"] = self.settings.feedback_apps_script_secret

        try:
            result = requests.post(
                self.settings.feedback_apps_script_url.strip(),
                json=payload,
                timeout=self.settings.feedback_apps_script_timeout,
            )
        except requests.RequestException as exc:
            raise RuntimeError(f"Feedback webhook request failed: {exc}") from exc

        if result.status_code >= 400:
            raise RuntimeError(
                f"Feedback webhook returned HTTP {result.status_code}: {result.text[:300]}"
            )

        try:
            data = result.json()
        except ValueError as exc:
            raise RuntimeError(
                f"Feedback webhook did not return JSON: {result.text[:300]}"
            ) from exc

        if str(data.get("status") or "").lower() not in {"ok", "logged"}:
            message = data.get("message") or data.get("error") or "Unknown webhook error."
            raise RuntimeError(f"Feedback webhook failed: {message}")

    def _get_worksheet(self) -> Any:
        if self._worksheet is not None:
            return self._worksheet

        if not self.settings.feedback_google_sheet_id:
            raise RuntimeError("FEEDBACK_GOOGLE_SHEET_ID is not configured.")

        client = self._get_gspread_client()
        spreadsheet = client.open_by_key(self.settings.feedback_google_sheet_id)
        worksheet = self._select_worksheet(spreadsheet)
        self._ensure_headers(worksheet)
        self._worksheet = worksheet
        return worksheet

    def _get_gspread_client(self) -> Any:
        try:
            import gspread
        except ImportError as exc:
            raise RuntimeError(
                "gspread is not installed. Run pip install -r requirements.txt."
            ) from exc

        credentials = self._service_account_dict()
        if credentials:
            return gspread.service_account_from_dict(credentials)

        credentials_file = self.settings.google_service_account_file.strip()
        if credentials_file:
            path = Path(credentials_file)
            if not path.is_absolute():
                path = self.settings.base_dir / path
            return gspread.service_account(filename=str(path))

        raise RuntimeError(
            "Google Sheets feedback logging is not configured. Set "
            "GOOGLE_SERVICE_ACCOUNT_JSON, GOOGLE_SERVICE_ACCOUNT_JSON_B64, or "
            "GOOGLE_APPLICATION_CREDENTIALS."
        )

    def _service_account_dict(self) -> dict[str, Any] | None:
        raw_json = self.settings.google_service_account_json.strip()
        raw_b64 = self.settings.google_service_account_json_b64.strip()

        if raw_b64:
            try:
                raw_json = base64.b64decode(raw_b64).decode("utf-8")
            except Exception as exc:
                raise RuntimeError(
                    "GOOGLE_SERVICE_ACCOUNT_JSON_B64 is not valid base64 JSON."
                ) from exc

        if not raw_json:
            return None

        try:
            parsed = json.loads(raw_json)
        except json.JSONDecodeError as exc:
            raise RuntimeError("GOOGLE_SERVICE_ACCOUNT_JSON is not valid JSON.") from exc

        if not isinstance(parsed, dict):
            raise RuntimeError("Google service account credentials must be a JSON object.")
        return parsed

    def _select_worksheet(self, spreadsheet: Any) -> Any:
        worksheet_name = self.settings.feedback_google_worksheet_name.strip()
        if worksheet_name:
            return spreadsheet.worksheet(worksheet_name)

        worksheet_gid = self.settings.feedback_google_worksheet_gid
        if worksheet_gid is not None:
            getter = getattr(spreadsheet, "get_worksheet_by_id", None)
            if getter:
                worksheet = getter(worksheet_gid)
                if worksheet:
                    return worksheet
            for worksheet in spreadsheet.worksheets():
                if getattr(worksheet, "id", None) == worksheet_gid:
                    return worksheet

        return spreadsheet.sheet1

    @staticmethod
    def _ensure_headers(worksheet: Any) -> None:
        values = worksheet.get("A1:C1")
        first_row = values[0] if values else []
        if any(str(cell).strip() for cell in first_row):
            return
        for cell, value in zip(("A1", "B1", "C1"), FEEDBACK_COLUMNS):
            worksheet.update_acell(cell, value)
