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
MAX_DUPLICATE_NAMES_SHOWN = 5
# Marks the warnings for duplicate rows, which drop no data: the first row wins.
DUPLICATE_WARNING_MARKER = " rows differ: "

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
            datasets[tab] = load_dataset(csv_text, header_first_cell)
        except requests.RequestException as e:
            logger.exception("Spreadsheet download failed", extra={"tab": tab})
            raise MetadataImportError(f"Could not download {tab}: {e!r}") from e
        except (UnicodeDecodeError, csv.Error, tablib.InvalidDimensions) as e:
            # E.g. an HTML login page served after a sharing change.
            logger.exception("Spreadsheet is not valid CSV", extra={"tab": tab})
            raise MetadataImportError(f"Could not read {tab} as CSV: {e!r}") from e

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
            if result.has_errors() or result.has_validation_errors():
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
    for r in results:
        if r.warnings:
            logger.warning(
                "Metadata import warnings for %s:\n%s",
                r.tab,
                "\n".join(r.warnings),
                extra={"tab": r.tab, "warnings": r.warnings},
            )
    return results


def _describe_errors(tab: str, result) -> str:
    lines = [f"Import of {tab} failed; nothing was changed."]
    for error in result.base_errors[:5]:
        lines.append(repr(error.error))
    for line, errors in result.row_errors()[:5]:
        for error in errors:
            lines.append(f"Line number: {line} - {error.error!r}")
    for invalid_row in result.invalid_rows[:5]:
        lines.append(f"Line number: {invalid_row.number} - {invalid_row.error!r}")
    return "\n".join(lines)


def format_results(results: list[TabResult]) -> list[str]:
    return [
        f"{r.tab}: {r.new} new, {r.updated} updated, {r.skipped} skipped, "
        f"{r.deleted} deleted"
        for r in results
    ]


def admin_warning_lines(results: list[TabResult]) -> list[str]:
    """Warnings for the admin, those meaning data was dropped first.

    Duplicate-row warnings drop nothing, so each tab's are collapsed into one
    line; the full list goes to the log.
    """
    dropped = []
    duplicate_lines = []
    for r in results:
        duplicates = []
        for warning in r.warnings:
            if DUPLICATE_WARNING_MARKER in warning:
                duplicates.append(warning.split(DUPLICATE_WARNING_MARKER, 1)[1])
            else:
                dropped.append(f"{r.tab}: {warning}")
        if duplicates:
            names = ", ".join(duplicates[:MAX_DUPLICATE_NAMES_SHOWN])
            if len(duplicates) > MAX_DUPLICATE_NAMES_SHOWN:
                names += ", ..."
            duplicate_lines.append(
                f"{r.tab}: {len(duplicates)} duplicate rows differ from the "
                f"first row, which was kept: {names}"
            )
    lines = dropped[:MAX_WARNINGS_SHOWN]
    if len(dropped) > MAX_WARNINGS_SHOWN:
        lines.append(
            f"... and {len(dropped) - MAX_WARNINGS_SHOWN} more warnings (see the log)"
        )
    return lines + duplicate_lines


def import_metadata_from_admin(admin_instance, request) -> HttpResponse:
    try:
        results = run_metadata_import()
    except MetadataImportError as e:
        admin_instance.message_user(request, str(e), level=messages.ERROR)
        return redirect(".")

    for line in format_results(results):
        admin_instance.message_user(request, line, level=messages.INFO)
    for line in admin_warning_lines(results):
        admin_instance.message_user(request, line, level=messages.WARNING)
    return redirect(".")
