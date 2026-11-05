from __future__ import annotations

import hashlib
import hmac
import os
import re
from base64 import b64decode, b64encode
from dataclasses import dataclass
from types import TracebackType
from typing import Literal, Self, TypeVar, cast
from urllib.parse import urlsplit, urlunsplit

import requests
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from pydantic import BaseModel, TypeAdapter, ValidationError

from kostal_models import (
    AuthClientFinal,
    AuthClientFirst,
    AuthCreateSessionRequest,
    AuthCreateSessionResponse,
    AuthServerFinal,
    AuthServerFirst,
    JsonValue,
    Module,
    PowerFlowValues,
    ProcessDataQuery,
    ProcessDataUpdate,
    User,
    Version,
)

JsonObject = dict[str, JsonValue]
Username = Literal["user", "master"]
ModelT = TypeVar("ModelT", bound=BaseModel)


class KostalApiError(Exception):
    pass


class KostalAuthenticationError(KostalApiError):
    pass


class KostalResponseError(KostalApiError):
    status_code: int
    message: str

    def __init__(self, status_code: int, message: str | None = None):
        self.status_code = status_code
        self.message = message or "Unknown API error"
        super().__init__(f"HTTP {status_code}: {self.message}")


class KostalProtocolError(KostalApiError):
    pass


@dataclass(frozen=True)
class KostalConfig:
    base_url: str
    username: str
    password: str
    service_code: str | None = None
    timeout_seconds: float = 10.0

    @classmethod
    def from_env(cls) -> KostalConfig:
        return cls(
            base_url=_normalize_base_url(os.environ["KOSTAL_BASE_URL"]),
            username=os.environ.get("KOSTAL_USERNAME", "user"),
            password=os.environ["KOSTAL_PASSWORD"],
            service_code=os.environ.get("KOSTAL_SERVICE_CODE") or None,
            timeout_seconds=float(os.environ.get("KOSTAL_TIMEOUT_SECONDS", "10")),
        )


def _normalize_base_url(raw_base_url: str) -> str:
    base_url = raw_base_url.strip()
    if not base_url:
        raise ValueError("KOSTAL_BASE_URL must not be empty.")

    if "://" not in base_url:
        base_url = f"http://{base_url}"

    parts = urlsplit(base_url)
    path = parts.path.rstrip("/")
    if not path:
        path = "/api/v1"
    elif path != "/api/v1":
        path = f"{path}/api/v1" if not path.endswith("/api/v1") else path

    return urlunsplit((parts.scheme, parts.netloc, path, "", ""))


class KostalApiClient:
    config: KostalConfig
    session: requests.Session
    session_id: str | None

    def __init__(self, config: KostalConfig):
        self.config = config
        self.session = requests.Session()
        self.session.headers.update({"Accept": "application/json"})
        self.session_id = None

    def __enter__(self) -> Self:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        try:
            if self.session_id is not None:
                self.logout()
        finally:
            self.session.close()

    def login(self) -> str:
        username = self.config.username
        password = self.config.password

        if username not in {"user", "master"}:
            raise ValueError("KOSTAL_USERNAME must be 'user' or 'master'.")
        if username == "master" and not self.config.service_code:
            raise ValueError("KOSTAL_SERVICE_CODE is required when KOSTAL_USERNAME=master.")
        api_username = cast(Username, username)

        client_nonce = os.urandom(12)
        client_nonce_b64 = b64encode(client_nonce).decode("utf-8")

        start_request = AuthClientFirst(username=api_username, nonce=client_nonce_b64)
        start_response = self._request(
            "POST",
            "auth/start",
            json=start_request.model_dump(mode="json"),
            authorized=False,
        )
        start_payload = self._parse_model(start_response, AuthServerFirst)

        server_nonce_b64 = start_payload.nonce
        transaction_id_b64 = start_payload.transactionId
        salt_b64 = start_payload.salt
        rounds = start_payload.rounds
        salt = b64decode(salt_b64)

        salted_password = hashlib.pbkdf2_hmac(
            "sha256", password.encode("utf-8"), salt, rounds
        )
        client_key = hmac.new(
            salted_password, b"Client Key", hashlib.sha256
        ).digest()
        stored_key = hashlib.sha256(client_key).digest()

        auth_message = (
            f"n={api_username},r={client_nonce_b64},r={server_nonce_b64},"
            f"s={salt_b64},i={rounds},c=biws,r={server_nonce_b64}"
        )

        client_signature = hmac.new(
            stored_key, auth_message.encode("utf-8"), hashlib.sha256
        ).digest()
        client_proof = bytes(a ^ b for a, b in zip(client_key, client_signature))

        server_key = hmac.new(
            salted_password, b"Server Key", hashlib.sha256
        ).digest()
        expected_server_signature = hmac.new(
            server_key, auth_message.encode("utf-8"), hashlib.sha256
        ).digest()

        finish_request = AuthClientFinal(
            transactionId=transaction_id_b64,
            proof=b64encode(client_proof).decode("utf-8"),
        )
        finish_response = self._request(
            "POST",
            "auth/finish",
            json=finish_request.model_dump(mode="json"),
            authorized=False,
        )
        finish_payload = self._parse_model(finish_response, AuthServerFinal)

        actual_server_signature = b64decode(finish_payload.signature)
        if actual_server_signature != expected_server_signature:
            raise KostalAuthenticationError("Server signature mismatch.")

        token = finish_payload.token
        if api_username == "master":
            token = f"{token}:{self.config.service_code}"

        session_key_hmac = hmac.new(stored_key, b"Session Key", hashlib.sha256)
        session_key_hmac.update(auth_message.encode("utf-8"))
        session_key_hmac.update(client_key)
        protocol_key = session_key_hmac.digest()

        iv = os.urandom(16)
        encrypted = AESGCM(protocol_key).encrypt(iv, token.encode("utf-8"), None)
        payload = encrypted[:-16]
        tag = encrypted[-16:]

        session_request = AuthCreateSessionRequest(
            transactionId=transaction_id_b64,
            iv=b64encode(iv).decode("utf-8"),
            tag=b64encode(tag).decode("utf-8"),
            payload=b64encode(payload).decode("utf-8"),
        )
        session_response = self._request(
            "POST",
            "auth/create_session",
            json=session_request.model_dump(mode="json"),
            authorized=False,
        )
        session_payload = self._parse_model(session_response, AuthCreateSessionResponse)

        self.session_id = session_payload.sessionId
        self.session.headers["Authorization"] = f"Session {self.session_id}"

        me = self.get_me()
        if not me.authenticated:
            raise KostalAuthenticationError("Session was created, but auth/me is not authenticated.")

        assert self.session_id is not None
        return self.session_id

    def logout(self) -> None:
        _ = self._request("POST", "auth/logout")
        _ = self.session.headers.pop("Authorization", None)
        self.session_id = None

    def get_version(self) -> Version:
        return self._parse_model(self._request("GET", "info/version", authorized=False), Version)

    def get_me(self) -> User:
        return self._parse_model(self._request("GET", "auth/me"), User)

    def get_modules(self) -> list[Module]:
        return self._parse_model_list(self._request("GET", "modules"), list[Module])

    def get_processdata_catalog(self) -> list[ProcessDataQuery]:
        return self._parse_model_list(
            self._request("GET", "processdata"), list[ProcessDataQuery]
        )

    def get_processdata_values(
        self, queries: list[ProcessDataQuery]
    ) -> list[ProcessDataUpdate]:
        return self._parse_model_list(
            self._request(
                "POST",
                "processdata",
                json=[query.model_dump(mode="json") for query in queries],
            ),
            list[ProcessDataUpdate],
        )

    def get_processdata_for_module(self, module_id: str) -> list[ProcessDataUpdate]:
        return self._parse_model_list(
            self._request("GET", f"processdata/{module_id}"), list[ProcessDataUpdate]
        )

    def get_power_flow_values(self) -> PowerFlowValues:
        catalog = self.get_processdata_catalog()
        available_ids = {
            entry.moduleid: set(entry.processdataids)
            for entry in catalog
        }
        pv_module_ids = sorted(
            module_id
            for module_id, processdata_ids in available_ids.items()
            if re.fullmatch(r"devices:local:pv\d+", module_id) and "P" in processdata_ids
        )

        if not pv_module_ids:
            raise KostalProtocolError(
                "No PV string modules exposing process-data id 'P' were found."
            )

        updates = self.get_processdata_values(
            [
                ProcessDataQuery(
                    moduleid="devices:local",
                    processdataids=["Home_P", "HomeGrid_P"],
                ),
                ProcessDataQuery(
                    moduleid="devices:local:battery",
                    processdataids=["P", "SoC"],
                ),
                *[
                    ProcessDataQuery(moduleid=module_id, processdataids=["P"])
                    for module_id in pv_module_ids
                ],
            ]
        )

        processdata_by_module = {
            update.moduleid: {item.id: item.value for item in update.processdata}
            for update in updates
        }

        local_values = processdata_by_module.get("devices:local")
        battery_values = processdata_by_module.get("devices:local:battery")

        if local_values is None:
            raise KostalProtocolError("Missing process data for module 'devices:local'.")
        if battery_values is None:
            raise KostalProtocolError(
                "Missing process data for module 'devices:local:battery'."
            )

        production_w = sum(
            self._require_processdata_value(
                processdata_by_module.get(module_id, {}),
                "P",
            )
            for module_id in pv_module_ids
        )
        house_consumption_w = self._require_processdata_value(local_values, "Home_P")
        grid_power_w = self._require_processdata_value(local_values, "HomeGrid_P")
        battery_power_w = self._require_processdata_value(battery_values, "P")
        battery_soc_percent = self._require_processdata_value(battery_values, "SoC")

        return PowerFlowValues(
            production_w=production_w,
            battery_charge_w=max(-battery_power_w, 0.0),
            battery_discharge_w=max(battery_power_w, 0.0),
            battery_soc_percent=battery_soc_percent,
            house_consumption_w=house_consumption_w,
            grid_import_w=max(grid_power_w, 0.0),
        )

    def _parse_model(self, response: requests.Response, model_type: type[ModelT]) -> ModelT:
        payload = self._json(response)
        try:
            return model_type.model_validate(payload)
        except ValidationError as exc:
            raise KostalProtocolError(
                f"Response from {response.request.method} {response.url} did not match {model_type.__name__}: {exc}"
            ) from exc

    def _parse_model_list(self, response: requests.Response, list_type: type[list[ModelT]]) -> list[ModelT]:
        payload = self._json(response)
        try:
            return TypeAdapter(list_type).validate_python(payload)
        except ValidationError as exc:
            raise KostalProtocolError(
                f"Response from {response.request.method} {response.url} did not match {list_type}: {exc}"
            ) from exc

    def _json(self, response: requests.Response) -> JsonValue:
        try:
            return cast(JsonValue, response.json())
        except ValueError as exc:
            content_type = response.headers.get("Content-Type", "unknown")
            body_preview = response.text.strip().replace("\n", " ")[:200]
            message = (
                f"Expected JSON response from {response.request.method} {response.url}, "
                f"got Content-Type '{content_type}' with body: {body_preview or '<empty>'}"
            )
            raise KostalProtocolError(
                message
            ) from exc

    def _request(
        self,
        method: str,
        path: str,
        *,
        authorized: bool = True,
        json: JsonValue | None = None,
    ) -> requests.Response:
        if authorized and self.session_id is None:
            raise KostalAuthenticationError("Call login() before using authenticated endpoints.")

        response = self.session.request(
            method,
            f"{self.config.base_url}/{path.lstrip('/')}",
            timeout=self.config.timeout_seconds,
            json=json,
        )

        if response.ok:
            return response

        message: str | None = None
        try:
            payload = cast(JsonValue, response.json())
        except ValueError:
            payload = None

        if isinstance(payload, dict):
            raw_message = payload.get("message")
            message = raw_message if isinstance(raw_message, str) else None

        if response.status_code in {400, 401, 403}:
            raise KostalAuthenticationError(message or response.text)

        raise KostalResponseError(response.status_code, message or response.text)

    def _require_processdata_value(
        self, processdata: dict[str, float], processdata_id: str
    ) -> float:
        value = processdata.get(processdata_id)
        if value is None:
            raise KostalProtocolError(
                f"Missing process-data value '{processdata_id}' in API response."
            )
        return value
