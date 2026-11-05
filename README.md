# kostal-scb

Small FastAPI service for reading live power-flow data from a KOSTAL inverter via its local REST API.

## What it exposes

The app currently exposes one endpoint:

- `GET /power_flow`

Response shape:

```json
{
  "production_w": 0,
  "battery_charge_w": 0,
  "battery_discharge_w": 0,
  "battery_soc_percent": 0,
  "house_consumption_w": 0,
  "grid_import_w": 0
}
```

Sample response:

```json
{
  "production_w": 8421.7,
  "battery_charge_w": 2150.0,
  "battery_discharge_w": 0.0,
  "battery_soc_percent": 63.0,
  "house_consumption_w": 3184.2,
  "grid_import_w": 0.0
}
```

Meaning of the values:

- `production_w`: total PV production, summed from available `devices:local:pvN/P` modules
- `battery_charge_w`: current charging power into the battery
- `battery_discharge_w`: current discharging power from the battery
- `battery_soc_percent`: current battery state of charge
- `house_consumption_w`: current house consumption
- `grid_import_w`: current power imported from the grid

## Requirements

- Python 3.15
- network access to the inverter
- valid inverter credentials

## Configuration

Do not store credentials or hostnames in Python. Use environment variables.

Example `.env`:

```env
KOSTAL_BASE_URL=http://your-device-host/api/v1
KOSTAL_USERNAME=user
KOSTAL_PASSWORD=your-password
# Only for master login:
# KOSTAL_SERVICE_CODE=your-service-code
# Optional:
# KOSTAL_TIMEOUT_SECONDS=10
```

Notes:

- `KOSTAL_BASE_URL` may be either `http://host` or `http://host/api/v1`
- the client normalizes the base URL to `/api/v1`
- every request to `/power_flow` logs into the real device and reads live data

## Local development

Install dependencies:

```bash
uv sync
```

Run the API:

```bash
uv run uvicorn main:app --reload
```

Open:

- API docs: `http://127.0.0.1:8000/docs`
- endpoint: `http://127.0.0.1:8000/power_flow`

Example request:

```bash
curl http://127.0.0.1:8000/power_flow
```

## Docker

Build the image:

```bash
docker build -t kostal-scb .
```

Run the container:

```bash
docker run --rm -p 8000:8000 --env-file .env kostal-scb
```

## Code structure

- `main.py` — FastAPI app and `/power_flow` endpoint
- `kostal_api.py` — REST client, auth workflow, and power-flow extraction
- `kostal_models.py` — Pydantic models derived from `swagger.json`
- `swagger.json` — local snapshot of the inverter API

## Verification

For changed Python files, run:

```bash
uvx basedpyright main.py kostal_api.py kostal_models.py
uvx ruff check main.py kostal_api.py kostal_models.py
uv run python -m py_compile main.py kostal_api.py kostal_models.py
```
