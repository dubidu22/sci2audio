"""Schemathesis against the server's own OpenAPI document (#7): for every operation, no
server error and every answer matches the schema (status, content type, body).

The app runs in process (ASGI) with the bearer token, so nothing listens on a port. Each
generated case is sent twice: as generated, and with its document and job ids replaced by
those of a real document and finished job, so the paths behind the 404s are checked too.

One built-in check is left out: `positive_data_acceptance` expects every schema-valid
request to succeed, but this API refuses schema-valid requests for reasons a schema can't
state (a file type sci2audio can't read, an unknown voice, a job already running, consent
not given); each of those answers has its own TestClient test.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import pytest
import schemathesis
from hypothesis import HealthCheck, settings
from schemathesis.specs.openapi.checks import positive_data_acceptance
from web_helpers import ORIGIN, make_config, pdf_bytes, program, upload, wait

from sci2audio.testing import no_network
from sci2audio.web import create_app

HOST = ORIGIN.removeprefix("http://")
EXAMPLES = 300 if os.environ.get("HYPOTHESIS_PROFILE") == "nightly" else 25


@pytest.fixture(scope="module")
def served(tmp_path_factory: pytest.TempPathFactory) -> dict[str, Any]:
    folder: Path = tmp_path_factory.mktemp("schemathesis")
    config = make_config(folder)
    app = create_app(config)
    client = program(app, config)
    doc = upload(client, pdf_bytes(), "seed.pdf")
    response = client.post("/api/v1/jobs", json={"kind": "script", "document": doc["id"]})
    job = wait(client, response.json()["id"])
    return {"app": app, "config": config, "document": doc["id"], "job": job["id"]}


@pytest.fixture(scope="module")
def api_schema(served: dict[str, Any]) -> Any:
    config = served["config"]
    return schemathesis.openapi.from_asgi(
        "/openapi.json",
        served["app"],
        headers={"Authorization": f"Bearer {config.token}", "Host": HOST},
    )


schema = schemathesis.pytest.from_fixture("api_schema")


@schema.parametrize()
@settings(
    max_examples=EXAMPLES,
    deadline=None,
    suppress_health_check=[HealthCheck.too_slow, HealthCheck.filter_too_much],
)
def test_the_api_matches_its_schema(case: Any, served: dict[str, Any]) -> None:
    config = served["config"]
    headers = {"Authorization": f"Bearer {config.token}", "Host": HOST}
    with no_network():
        case.call_and_validate(headers=headers, excluded_checks=[positive_data_acceptance])
        known = {"document_id": served["document"], "job_id": served["job"]}
        replaced = {
            key: known.get(key, value) for key, value in (case.path_parameters or {}).items()
        }
        if replaced != (case.path_parameters or {}):
            case.path_parameters = replaced
            case.call_and_validate(headers=headers, excluded_checks=[positive_data_acceptance])
