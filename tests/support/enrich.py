"""Fakes for enrichment tests: a transport with canned answers, a clock and fpcalc."""

import json
import re
import subprocess
import urllib.parse
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from tunedex.enrich.http import Response, TransportError

FIXTURES = Path(__file__).parents[1] / "fixtures" / "enrich"


@dataclass
class FakeClock:
    now: float = 0.0
    slept: list[float] = field(default_factory=list[float])

    def __call__(self) -> float:
        return self.now

    def sleep(self, seconds: float) -> None:
        self.slept.append(seconds)
        self.now += seconds


@dataclass
class FakeTransport:
    """Answers by URL prefix; records every request."""

    answers: dict[str, list[Response | Exception]] = field(
        default_factory=dict[str, list[Response | Exception]]
    )
    routes: list[tuple[str, Callable[[str, Mapping[str, str] | None], Any]]] = field(
        default_factory=list
    )
    requests: list[tuple[str, str, Mapping[str, str] | None, Mapping[str, str]]] = field(
        default_factory=list
    )

    def queue(self, prefix: str, *answers: Response | Exception) -> None:
        self.answers.setdefault(prefix, []).extend(answers)

    def route(self, prefix: str, answer: Callable[[str, Mapping[str, str] | None], Any]) -> None:
        """Answer every request starting with ``prefix`` with ``answer(url, data)`` as JSON."""
        self.routes.append((prefix, answer))

    def request(
        self, method: str, url: str, data: Mapping[str, str] | None, headers: Mapping[str, str]
    ) -> Response:
        self.requests.append((method, url, data, headers))
        for prefix, queued in self.answers.items():
            if url.startswith(prefix) and queued:
                answer = queued.pop(0)
                if isinstance(answer, Exception):
                    raise answer
                return answer
        for prefix, answer in self.routes:
            if url.startswith(prefix):
                value = answer(url, data)
                if isinstance(value, Response):
                    return value
                return Response(200, json.dumps(value).encode())
        raise TransportError(f"no fake answer for {url}")


def ok(value: Any) -> Response:
    return Response(200, json.dumps(value).encode())


@dataclass
class FakeFpcalc:
    """Stands in for ``subprocess.run`` of fpcalc: a fingerprint per file name."""

    prints: dict[str, tuple[float, str]] = field(default_factory=dict[str, tuple[float, str]])
    calls: list[str] = field(default_factory=list[str])

    def __call__(self, arguments: list[str], **_kwargs: object) -> subprocess.CompletedProcess[str]:
        path = arguments[-1]
        self.calls.append(path)
        name = Path(path).name
        if name not in self.prints:
            return subprocess.CompletedProcess(arguments, 2, "", "ERROR: cannot decode")
        duration, fingerprint = self.prints[name]
        out = json.dumps({"duration": duration, "fingerprint": fingerprint})
        return subprocess.CompletedProcess(arguments, 0, out, "")


def fixture(name: str) -> Any:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def search_fixture(url: str) -> str:
    """The fixture name of a recording search: ``search-<title>-<artist id[:8]>.json``."""
    query = urllib.parse.parse_qs(urllib.parse.urlsplit(url).query)["query"][0]
    found = re.fullmatch(r'recording:"(.*)" AND arid:([0-9a-f-]+)', query)
    assert found is not None, query
    title = re.sub(r"[^a-z0-9]+", "-", found[1].casefold()).strip("-")
    return f"search-{title}-{found[2][:8]}.json"


def catalogue(lookups: Mapping[str, Any]) -> FakeTransport:
    """A transport answering like AcoustID and MusicBrainz from the recorded fixtures.

    ``lookups`` maps a fingerprint to the AcoustID answer for it; MusicBrainz recordings,
    releases and searches come from ``recording-<id>.json``, ``release-<id>.json`` and
    ``search-<title>-<artist>.json``.
    """
    transport = FakeTransport()

    def lookup(_url: str, data: Mapping[str, str] | None) -> Any:
        assert data is not None
        return lookups[data["fingerprint"]]

    def entity(url: str, _data: Mapping[str, str] | None) -> Any:
        kind, rest = url.removeprefix("https://musicbrainz.org/ws/2/").split("/", 1)
        if rest.startswith("?"):
            path = FIXTURES / search_fixture(url)
        else:
            path = FIXTURES / f"{kind}-{rest.split('?', 1)[0]}.json"
        if not path.exists():
            return Response(404, b'{"error": "Not Found"}')
        return fixture(path.name)

    transport.route("https://api.acoustid.org/", lookup)
    transport.route("https://musicbrainz.org/", entity)
    return transport


def answer(recording_id: str, *, score: float = 0.98, title: str, duration: float) -> Any:
    """An AcoustID answer with one recording."""
    recording = {"id": recording_id, "title": title, "duration": duration}
    return {"status": "ok", "results": [{"score": score, "recordings": [recording]}]}
