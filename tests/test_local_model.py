from pathlib import Path
from typing import Any

import pytest

from archaeo.errors import PipelineError
from archaeo.local_model import OllamaClient, Review, review_images

RESULT = {
    "recommendation": "uncertain",
    "visible_structures": ["lineare Struktur"],
    "alternative_explanations": ["Weg"],
    "limitations": ["Einzelbild"],
    "explanation": "Eine fachliche Prüfung ist erforderlich.",
}


class FakeClient(OllamaClient):
    def __init__(self) -> None:
        super().__init__("fixture:latest")
        self.calls = 0

    def identity(self) -> dict[str, Any]:
        return {"model": self.model, "digest": "fixture-digest"}

    def review(self, image: bytes) -> Review:
        self.calls += 1
        return Review.model_validate(RESULT)


def test_cache_and_manifest(tmp_path: Path) -> None:
    import json

    folder = tmp_path / "images"
    folder.mkdir()
    (folder / "tile.png").write_bytes(b"\x89PNG\r\n\x1a\nfixture")
    client = FakeClient()
    result = review_images(folder, tmp_path / "out", client)
    report = json.loads(result.read_text())
    assert report["model"]["digest"] == "fixture-digest"
    assert report["results"][0]["review"]["recommendation"] == "uncertain"
    review_images(folder, tmp_path / "out", client)
    assert client.calls == 1
    (folder / "tile.png").write_bytes(b"\x89PNG\r\n\x1a\nchanged")
    review_images(folder, tmp_path / "out", client)
    assert client.calls == 2


def test_preflight_limits(tmp_path: Path) -> None:
    folder = tmp_path / "images"
    folder.mkdir()
    client = FakeClient()
    with pytest.raises(PipelineError, match="Keine PNG"):
        review_images(folder, tmp_path / "out", client)
    (folder / "bad.png").write_bytes(b"not an image")
    with pytest.raises(PipelineError, match="Dateikopf"):
        review_images(folder, tmp_path / "out", client)
    (folder / "second.png").write_bytes(b"anything")
    with pytest.raises(PipelineError, match="Bildlimit"):
        review_images(folder, tmp_path / "out", client, max_images=1)
    assert client.calls == 0


def test_model_response_schema(monkeypatch: pytest.MonkeyPatch) -> None:
    import json

    client = OllamaClient("fixture:latest")

    def respond(route: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        assert route == "/api/chat"
        assert payload is not None and payload["stream"] is False
        assert payload["messages"][0]["images"]
        return {"done": True, "message": {"content": json.dumps(RESULT)}}

    monkeypatch.setattr(client, "_request", respond)
    assert client.review(b"image").recommendation == "uncertain"
    monkeypatch.setattr(client, "_request", lambda *a: {"done": True, "message": {"content": "{}"}})
    with pytest.raises(PipelineError, match="Schema"):
        client.review(b"image")
    monkeypatch.setattr(client, "_request", lambda *a: {"done": False})
    with pytest.raises(PipelineError, match="Unvollständige"):
        client.review(b"image")


def test_local_identity_and_cloud_rejection(monkeypatch: pytest.MonkeyPatch) -> None:
    with pytest.raises(PipelineError):
        OllamaClient("model:cloud")
    client = OllamaClient("fixture")

    def respond(route: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        if route == "/api/show":
            return {"capabilities": ["vision"], "details": {"family": "fixture"}}
        assert route == "/api/tags" and payload is None
        return {"models": [{"name": "fixture:latest", "digest": "sha256"}]}

    monkeypatch.setattr(client, "_request", respond)
    assert client.identity()["digest"] == "sha256"
    monkeypatch.setattr(client, "_request", lambda *a: {"remote_host": "https://cloud.example"})
    with pytest.raises(PipelineError, match="Cloud"):
        client.identity()
    monkeypatch.setattr(client, "_request", lambda *a: {"capabilities": ["completion"]})
    with pytest.raises(PipelineError, match="Bildeingaben"):
        client.identity()


def test_network_transport_no_proxy_no_redirect() -> None:
    from archaeo.local_model import NoRedirect

    client = OllamaClient("fixture")
    assert client.endpoint == "http://127.0.0.1:11434"
    assert not any(type(h).__name__ == "ProxyHandler" for h in client.opener.handlers)
    with pytest.raises(PipelineError, match="Redirect"):
        NoRedirect().redirect_request(None, None, 302, "", None, "https://cloud.example")
