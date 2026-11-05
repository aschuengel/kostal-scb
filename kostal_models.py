from __future__ import annotations

from datetime import date, datetime
from typing import ClassVar, Literal

from pydantic import BaseModel, ConfigDict

type JsonScalar = None | bool | int | float | str
type JsonValue = JsonScalar | list["JsonValue"] | dict[str, "JsonValue"]


class KostalModel(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(extra="ignore")


class Error(KostalModel):
    message: str


class User(KostalModel):
    role: str
    permissions: list[str]
    active: bool
    authenticated: bool
    anonymous: bool
    locked: bool


class AuthClientFirst(KostalModel):
    username: Literal["user", "master"]
    nonce: str


class AuthServerFirst(KostalModel):
    transactionId: str
    nonce: str
    salt: str
    rounds: int


class AuthClientFinal(KostalModel):
    transactionId: str
    proof: str


class AuthServerFinal(KostalModel):
    signature: str
    token: str


class AuthCreateSessionRequest(KostalModel):
    transactionId: str
    iv: str
    tag: str
    payload: str


class AuthCreateSessionResponse(KostalModel):
    sessionId: str


class AuthSetPasswordRequest(KostalModel):
    transactionId: str
    iv: str
    tag: str
    payload: str


class EventsQuery(KostalModel):
    language: Literal[
        "de-de",
        "en-gb",
        "es-es",
        "fr-fr",
        "it-it",
        "nl-nl",
        "pl-pl",
        "pt-pt",
        "cs-cz",
        "el-gr",
        "da-dk",
        "et-ee",
        "fi-fi",
        "sv-se",
    ] = "en-gb"
    max: int = 10


class Event(KostalModel):
    code: int
    start_time: datetime
    end_time: datetime | None = None
    is_active: bool
    category: Literal["info", "warning", "error"]
    group: str
    description: str
    long_description: str | None = None
    acknowledge: bool


class EventAck(KostalModel):
    code: int = 0


class FirmwareUpdateProgress(KostalModel):
    status: Literal[
        "idle",
        "controllerprecheck",
        "preprocessing",
        "controllerstartbootloader",
        "updateflasherase",
        "updatedownloadprogram",
        "updateverify",
        "controllerstartapplication",
        "postprocessing",
        "successful",
        "error",
    ]
    target: str
    current_percent: int


class Version(KostalModel):
    name: str
    api_version: str
    sw_version: str
    hostname: str


class DownloadRequest(KostalModel):
    begin: date | None = None
    end: date | None = None


class Module(KostalModel):
    id: str
    type: str


class ProcessDataQuery(KostalModel):
    moduleid: str
    processdataids: list[str]


class ProcessData(KostalModel):
    id: str
    unit: str | None = None
    value: float


class ProcessDataUpdate(KostalModel):
    moduleid: str
    processdata: list[ProcessData]


class PowerFlowValues(KostalModel):
    production_w: float
    battery_charge_w: float
    battery_discharge_w: float
    battery_soc_percent: float
    house_consumption_w: float
    grid_import_w: float


class Setting(KostalModel):
    id: str
    value: str


class SettingsUpdate(KostalModel):
    moduleid: str
    settings: list[Setting]


class SettingsQuery(KostalModel):
    moduleid: str
    settingids: list[str]


class SettingMetadata(KostalModel):
    id: str
    unit: str | None = None
    type: JsonValue | None = None
    min: str | None = None
    max: str | None = None
    default: str | None = None
    access: JsonValue | None = None


class SettingsMetadata(KostalModel):
    moduleid: str
    settings: list[SettingMetadata]


class UpdateStatus(KostalModel):
    current_status: Literal["idle", "start", "run", "success", "failure", "download", "done"]
    last_status: Literal["idle", "start", "run", "success", "failure", "download", "done"]
    error: int


class UpdateProgress(KostalModel):
    status: Literal["idle", "start", "run", "success", "failure", "download", "done"]
    source: Literal["local", "automatic", "download"]
    download_percent: int
    steps: int
    current_step: int
    current_percent: int


class Status(KostalModel):
    status: UpdateStatus
    progress: UpdateProgress | None = None
