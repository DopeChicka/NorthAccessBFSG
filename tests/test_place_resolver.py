from pathlib import Path

import pytest

from app.discovery.place_resolver import (
    PlaceDataError,
    PlaceNotFoundError,
    load_places,
    resolve_city,
)


def write_city_csv(path: Path, content: str) -> Path:
    path.write_text(content, encoding="utf-8")
    return path


def test_luebeck_umlaut_resolves_from_canonical_data() -> None:
    matches = resolve_city("Lübeck")

    assert matches
    assert {match.city for match in matches} == {"Lübeck"}
    assert any(match.postal_code == "23552" for match in matches)
    assert all(match.country == "DE" for match in matches)


def test_luebeck_transliteration_resolves_from_canonical_data() -> None:
    matches = resolve_city("Luebeck")

    assert matches
    assert {match.city for match in matches} == {"Lübeck"}


def test_lubeck_plain_ascii_resolves_from_canonical_data() -> None:
    matches = resolve_city("lubeck")

    assert matches
    assert {match.city for match in matches} == {"Lübeck"}


def test_unknown_city_fails_clearly(tmp_path: Path) -> None:
    data_file = write_city_csv(tmp_path / "places.csv", "plz;stadt\n23552;Lübeck\n")

    with pytest.raises(PlaceNotFoundError, match="No places found for city: Atlantis"):
        resolve_city("Atlantis", data_file)


def test_header_only_csv_fails_clearly(tmp_path: Path) -> None:
    data_file = write_city_csv(tmp_path / "places.csv", "plz;stadt\n")

    with pytest.raises(PlaceDataError, match="no usable city rows"):
        load_places(data_file)


def test_substring_special_recipients_do_not_pollute_exact_city_match(tmp_path: Path) -> None:
    data_file = write_city_csv(
        tmp_path / "places.csv",
        "plz;stadt\n"
        "23552;Lübeck\n"
        "23560;Stadtwerke Lübeck Gruppe GmbH\n"
        "23558;Finanzamt Lübeck\n"
        "23556;Agentur für Arbeit Lübeck\n",
    )

    matches = resolve_city("Luebeck", data_file)

    assert [match.city for match in matches] == ["Lübeck"]
    assert [match.postal_code for match in matches] == ["23552"]
