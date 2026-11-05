import dotenv
from fastapi import FastAPI, HTTPException

from kostal_api import (
    KostalApiClient,
    KostalApiError,
    KostalAuthenticationError,
    KostalConfig,
    KostalProtocolError,
    KostalResponseError,
)
from kostal_models import PowerFlowValues

_ = dotenv.load_dotenv()

app = FastAPI(title="kostal-scb")


@app.get("/power_flow", response_model=PowerFlowValues)
def get_power_flow() -> PowerFlowValues:
    try:
        config = KostalConfig.from_env()
        with KostalApiClient(config) as client:
            _ = client.login()
            return client.get_power_flow_values()
    except KostalAuthenticationError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc
    except KostalProtocolError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except KostalResponseError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except (KostalApiError, ValueError) as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
