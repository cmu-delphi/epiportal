import re

import tablib
from django.db.models import Max
from epiweeks import Week

from base.models import GeographicScope, Geography, Pathogen, SeverityPyramidRung
from base.resources import get_geographic_mapping_by_name

ISO_DATE_RE = re.compile(r"^(\d{4}-\d{2}-\d{2})(?:[ T].*)?$")
EPIWEEK_RE = re.compile(r"^(\d{4})(?:-?[wW](\d{1,2})|(\d{2}))$")


def parse_bool(value) -> bool:
    return str(value).strip().lower() == "true"


def normalize_sheet_date(value: str | None) -> str:
    """Return an ISO date for dates and epiweeks (CDC Sunday start); other text is kept."""
    text = (value or "").strip()
    iso_match = ISO_DATE_RE.match(text)
    if iso_match:
        return iso_match.group(1)
    epiweek_match = EPIWEEK_RE.match(text)
    if epiweek_match:
        year = int(epiweek_match.group(1))
        week = int(epiweek_match.group(2) or epiweek_match.group(3))
        return Week(year, week).startdate().isoformat()
    return text


def split_list(value: str | None) -> list[str]:
    return [item.strip() for item in (value or "").split(",") if item.strip()]


def drop_duplicate_rows(dataset: tablib.Dataset, key_column: str) -> list[str]:
    """
    Keep the first row per key and drop later ones in place.

    Returns the keys whose duplicate rows differed from the first one.
    Rows with an empty key are left alone.
    """
    first_rows: dict[str, tuple] = {}
    differing: list[str] = []
    keep: list[tuple] = []
    key_index = dataset.headers.index(key_column)
    for row in dataset:
        row = tuple(row)
        key = row[key_index]
        if not key:
            keep.append(row)
        elif key not in first_rows:
            first_rows[key] = row
            keep.append(row)
        elif row != first_rows[key] and key not in differing:
            differing.append(key)
    headers = dataset.headers
    dataset.wipe()
    dataset.headers = headers
    for row in keep:
        dataset.append(row)
    return differing


def pathogen_ids(value: str, used_in: str) -> str:
    ids = []
    for name in split_list(value):
        pathogen, _ = Pathogen.objects.get_or_create(
            name=name,
            used_in=used_in,
            defaults={"display_name": name},
        )
        ids.append(pathogen.id)
    return ",".join(map(str, ids))


def geography_ids(value: str, used_in: str) -> str:
    ids = []
    for name in split_list(value):
        defaults = {"used_in": used_in}
        result = get_geographic_mapping_by_name(name)
        if result:
            name, mapping = result
            defaults.update(mapping)
        else:
            max_order = Geography.objects.filter(used_in=used_in).aggregate(
                Max("display_order_number")
            )["display_order_number__max"]
            defaults["display_order_number"] = (max_order or 0) + 1
        geography, _ = Geography.objects.get_or_create(
            name=name, used_in=used_in, defaults=defaults
        )
        ids.append(geography.id)
    return ",".join(map(str, ids))


def severity_pyramid_rung_ids(
    value: str, used_in: str, empty_as_na: bool = False
) -> str:
    names = split_list(value)
    if not names and empty_as_na:
        names = ["N/A"]
    ids = []
    for name in names:
        rung, _ = SeverityPyramidRung.objects.get_or_create(
            name=name,
            used_in=used_in,
            defaults={"display_name": name if name == "N/A" else name.capitalize()},
        )
        ids.append(rung.id)
    return ",".join(map(str, ids))


def geographic_scope_id(value: str, used_in: str) -> int | None:
    name = (value or "").strip()
    if not name:
        return None
    scope, _ = GeographicScope.objects.get_or_create(name=name, used_in=used_in)
    return scope.id
