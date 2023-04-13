"""API for super productivity."""
from __future__ import annotations

import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Iterator, Optional

from dropbox.dropbox_client import Dropbox  # type: ignore
from dropbox.files import WriteMode  # type: ignore


class SupProd():
    """Main Super-productivity module."""

    def __init__(self, api_key, refresh_token,
                 file_path="/Apps/super_productivity/super_productivity/sp.json"):
        """Init."""
        self.refresh_token = refresh_token
        self.api_key = api_key
        self._dropbox = None
        self._file_path = file_path

    @staticmethod
    def from_config(file_path=Path("~/.config/tmq/super_productivity.json")) -> SupProd:
        """Load from config file."""
        with open(file_path.expanduser(), "r") as f:
            return SupProd(**json.load(f))

    @property
    def dropbox(self) -> Dropbox:
        """Get file."""
        if self._dropbox is None:
            self._dropbox = Dropbox(oauth2_refresh_token=self.refresh_token, app_key=self.api_key)
        return self._dropbox

    @property
    def contents(self):
        """Get file contents."""
        res = self.dropbox.files_download(self._file_path)[1]
        ret = res.json()
        res.close()
        return ret

    def set_color(self, color: str) -> None:
        """Set color of default theme."""
        content = self.contents
        content["tag"]["entities"]["TODAY"]["theme"]["primary"] = color
        content["tag"]["entities"]["TODAY"]["theme"]["accent"] = color
        self.update_contents(content)

    def update_contents(self, contents):
        contents["lastLocalSyncModelChange"] = int(time.time() * 1000)
        self.dropbox.files_upload(
            json.dumps(contents).encode(),
            self._file_path,
            mode=WriteMode('overwrite')
        )

    def new_task_id(self):
        i = 1
        contents = self.contents["task"]["ids"]
        while True:
            if str(i) in contents:
                i += 1

            else:
                return str(i)

    @property
    def tasks(self):
        return [x for x in self.all_tasks if not x.done]

    @property
    def all_tasks(self):
        contents = self.contents["task"]
        return [Task(self, x, contents["entities"][x]) for x in contents["ids"]]

    @property
    def default_project_id(self) -> Optional[str]:
        """Fetch default project id."""
        try:
            return self.contents["globalConfig"]["misc"]["defaultProjectId"] or None
        except KeyError:
            return None

    def get_task_by_title(self, title):
        candidates = [x for x in self.tasks if x.title == title]
        if candidates:
            return candidates[0]

        return None

    def create_task(self, task_title, project_id=None, is_today=True, is_unique=False, time_estimate=0,
                    attachments: Iterable[Attachment] = []) -> None:
        """Create task."""
        project_id = project_id or self.default_project_id
        urls = list(attachments) or []

        if is_unique and (self.get_task_by_title(task_title) is not None):
            return

        task_id = self.new_task_id()
        contents = self.contents
        contents["task"]["ids"].append(task_id)
        contents["task"]["entities"][task_id] = {
            "title": task_title,
            "projectId": project_id,
            "id": task_id,
            "isDone": False,
            "subTaskIds": [],
            "timeSpentOnDay": {},
            "timeSpent": 0,
            "timeEstimate": time_estimate,
            "doneOn": None,
            "reminderId": None,
            "notes": "",
            "tagIds": [],
            "parentId": None,
            "plannedAt": None,
            "_showSubtasksMode": 2,
            "attachments": list(map(lambda x: x.attachment, urls)),
            "issueId": None,
            "issuePoints": None,
            "issueType": None,
            "issueAttachmentNr": None,
            "issueLastUpdated": None,
            "issueWasUpdated": None,
        }

        if project_id is not None:
            contents["project"]["entities"][project_id]["taskIds"].append(task_id)

        if is_today or project_id is None:
            contents["task"]["entities"][task_id]["tagIds"].append("TODAY")
            contents["tag"]["entities"]["TODAY"]["taskIds"].append(task_id)
        self.update_contents(contents)

    def create_tasks(self, iter: Iterator[str]) -> None:
        """Create tasks for project."""
        for task in iter:
            self.create_task(task)

    def cleanup_manual(self):
        contents = self.contents
        for x in contents["task"]["ids"]:
            try:
                int(x)
                contents["task"]["entities"].pop(x)
                contents["task"]["ids"].remove(x)
                contents["project"]["entities"]["DEFAULT"]["taskIds"].remove(x)
                contents["tag"]["entities"]["TODAY"]["taskIds"].remove(x)
            except AttributeError:
                pass

        self.update_contents(contents)

    @property
    def projects(self):
        contents = self.contents["project"]
        return [Project(self, x, contents["entities"][x]) for x in contents["ids"]]

    def get_project_by_name(self, name: str, case_insensitive: bool = True) -> Project:
        """Get a project by name."""
        if case_insensitive:
            name = name.lower()
        for x in self.projects:
            if (x.title.lower() if case_insensitive else x.title) == name:
                return x
        raise ValueError(f"Project with name {name} not found.")

    @property
    def todays_tasks(self):
        return self.get_tasks_with_tag("TODAY")

    def get_tasks_with_tag(self, tag):
        return [x for x in self.tasks if tag in x.tags]


class Task:

    """Task module"""

    def __init__(self, module, task_id, task_details):
        """Generate task object from tasks file

        :task_id: TODO
        :task_details: TODO

        """
        self._module = module
        self._task_details = task_details

    @property
    def title(self):
        return self._task_details["title"].strip()

    @property
    def done(self):
        return self._task_details["isDone"]

    @property
    def done_at(self):
        return self._task_details["doneOn"] \
            / 1000.0 if self._task_details["doneOn"] is not None else 0

    @property
    def project_id(self):
        return self._task_details["projectId"]

    @property
    def tags(self):
        return self._task_details["tagIds"]

    @property
    def attachments(self) -> Iterator[Attachment]:
        """Iterate attachments."""
        return map(Attachment.from_attachment, self._task_details["attachments"])


class Project:

    def __init__(self, module, project_id, project_details):
        self._module = module
        self._project_details = project_details
        self._project_id = project_id

    @property
    def id(self) -> str:
        return self._project_id

    @property
    def tasks(self):
        return [x for x in self._module.tasks if x.project_id == self._project_id]

    @property
    def all_tasks(self):
        return [x for x in self._module.all_tasks if x.project_id == self._project_id]

    def create_task(self, *args, **kwargs):
        return self._module.create_task(*args, project_id=self._project_id, **kwargs)

    def create_tasks(self, iter: Iterator[str], *args, **kwargs) -> None:
        """Create tasks for project."""
        for task in iter:
            self.create_task(task, *args, **kwargs)

    @property
    def title(self) -> str:
        """Get project title."""
        return self._project_details["title"]


@dataclass
class Attachment:
    """Attachment repr."""

    path: str
    title: str
    attachment_type: str = "LINK"

    @staticmethod
    def from_attachment(attachment: dict[str, str]) -> Attachment:
        """Get from attachment."""
        return Attachment(attachment["path"], attachment["title"], attachment["type"])

    @property
    def attachment(self) -> dict[str, str]:
        """Return a valid attachment."""
        return {
            "type": self.attachment_type,
            "path": self.path,
            "title": self.title,
            "id": str(time.time())
        }
