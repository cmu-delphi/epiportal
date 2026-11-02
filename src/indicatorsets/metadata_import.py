"""Import every tab of the metadata sheet in one ordered, atomic run.

The tabs depend on each other (an indicator names its set and source, a
dashboard row names an indicator), so they are imported in that order inside
one transaction: a failure anywhere leaves the database exactly as it was.
"""

import csv
import logging
from dataclasses import dataclass, field
from io import StringIO
from typing import Callable

import requests
import tablib
from django.conf import settings
from django.contrib import messages
from django.db import transaction
from django.http import HttpResponse
from django.shortcuts import redirect
from import_export.results import RowResult

from alternative_interface.resources import ExpressViewIndicatorResource
from datasources.resources import SourceSubdivisionResource
from indicators.resources import IndicatorResource
from indicatorsets.resources import IndicatorSetResource

logger = logging.getLogger(__name__)

MAX_WARNINGS_SHOWN = 20

# (settings key, resource class, first header cell when the tab has a preamble)
TABS = (
    ("sources", SourceSubdivisionResource, None),
    ("indicator_sets", IndicatorSetResource, None),
    ("indicators", IndicatorResource, None),
    ("express_view_indicators", ExpressViewIndicatorResource, "Menu Item"),
)


@dataclass
class TabResult:
    tab: str
    new: int = 0
    updated: int = 0
    skipped: int = 0
    deleted: int = 0
    warnings: list[str] = field(default_factory=list)


class MetadataImportError(Exception):
    pass


def fetch_csv(url: str) -> str:
    response = requests.get(url, timeout=(5, 30))
    response.raise_for_status()
    return response.content.decode("utf-8")


def load_dataset(csv_text: str, header_first_cell: str | None = None) -> tablib.Dataset:
    """Parse CSV text, dropping any preamble before the header row.

    The preamble may hold multi-line quoted cells, so rows are found by
    parsing rather than by counting lines.
    """
    if header_first_cell is not None:
        # Parse with csv, not tablib: the preamble's width differs from the
        # table's, which tablib rejects.
        rows = list(csv.reader(StringIO(csv_text)))
        for index, row in enumerate(rows):
            if row and row[0] == header_first_cell:
                break
        else:
            raise MetadataImportError(
                f"Header row starting with {header_first_cell!r} not found"
            )
        out = StringIO()
        csv.writer(out).writerows(rows[index:])
        csv_text = out.getvalue()
    return tablib.Dataset().load(csv_text, format="csv")


def run_metadata_import(
    fetch: Callable[[str], str] = fetch_csv,
) -> list[TabResult]:
    # Download everything before writing anything.
    datasets = {}
    for tab, _resource_class, header_first_cell in TABS:
        try:
            csv_text = fetch(settings.SPREADSHEET_URLS[tab])
        except requests.RequestException as e:
            logger.exception("Spreadsheet download failed", extra={"tab": tab})
            raise MetadataImportError(f"Could not download {tab}: {e!r}") from e
        datasets[tab] = load_dataset(csv_text, header_first_cell)

    results = []
    with transaction.atomic():
        for tab, resource_class, _header_first_cell in TABS:
            resource = resource_class()
            result = resource.import_data(
                datasets[tab],
                dry_run=False,
                raise_errors=False,
                collect_failed_rows=True,
            )
            if result.has_errors():
                raise MetadataImportError(_describe_errors(tab, result))
            results.append(
                TabResult(
                    tab=tab,
                    new=result.totals[RowResult.IMPORT_TYPE_NEW],
                    updated=result.totals[RowResult.IMPORT_TYPE_UPDATE],
                    skipped=result.totals[RowResult.IMPORT_TYPE_SKIP],
                    deleted=resource.deleted_count,
                    warnings=list(resource.warnings),
                )
            )
    return results


def _describe_errors(tab: str, result) -> str:
    lines = [f"Import of {tab} failed; nothing was changed."]
    for error in result.base_errors[:5]:
        lines.append(repr(error.error))
    for line, errors in result.row_errors()[:5]:
        for error in errors:
            lines.append(f"Line number: {line} - {error.error!r}")
    return "\n".join(lines)


def format_results(results: list[TabResult]) -> list[str]:
    return [
        f"{r.tab}: {r.new} new, {r.updated} updated, {r.skipped} skipped, "
        f"{r.deleted} deleted"
        for r in results
    ]


def import_metadata_from_admin(admin_instance, request) -> HttpResponse:
    try:
        results = run_metadata_import()
    except MetadataImportError as e:
        admin_instance.message_user(request, str(e), level=messages.ERROR)
        return redirect(".")

    lines = format_results(results)
    warnings = [warning for r in results for warning in r.warnings]
    lines.extend(warnings[:MAX_WARNINGS_SHOWN])
    if len(warnings) > MAX_WARNINGS_SHOWN:
        lines.append(f"... and {len(warnings) - MAX_WARNINGS_SHOWN} more warnings")
    admin_instance.message_user(request, "\n".join(lines), level=messages.INFO)
    return redirect(".")
