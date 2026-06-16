from io import BytesIO, TextIOWrapper

import requests
from django.contrib import messages
from django.shortcuts import redirect
from django.utils.module_loading import import_string
from django.http import FileResponse
from import_export.results import RowResult
from delphi_utils import get_structured_logger

logger = get_structured_logger("base.utils")


def import_data(admin_instance, request, resource_class, spreadsheet_url):
    resource = resource_class()
    format_class = import_string("import_export.formats.base_formats.CSV")

    try:
        response = requests.get(spreadsheet_url, timeout=(5, 30))
        response.raise_for_status()
    except requests.Timeout:
        logger.exception(
            "Spreadsheet download timed out", extra={"url": spreadsheet_url}
        )
        admin_instance.message_user(
            request,
            "Import failed: the spreadsheet server did not respond in time. Please try again.",
            level=messages.ERROR,
        )
        return redirect(".")
    except requests.HTTPError as e:
        status = e.response.status_code if e.response is not None else "unknown"
        logger.exception(
            "Spreadsheet download returned HTTP error",
            extra={"url": spreadsheet_url, "status": status},
        )
        admin_instance.message_user(
            request,
            f"Import failed: spreadsheet server returned HTTP {status}. "
            "Check that the spreadsheet is published and the URL is correct.",
            level=messages.ERROR,
        )
        return redirect(".")
    except requests.RequestException:
        logger.exception("Spreadsheet download failed", extra={"url": spreadsheet_url})
        admin_instance.message_user(
            request,
            "Import failed: could not reach the spreadsheet server. Please try again later.",
            level=messages.ERROR,
        )
        return redirect(".")

    csvfile = TextIOWrapper(BytesIO(response.content), encoding="utf-8")

    dataset = format_class().create_dataset(csvfile.read())

    result = resource.import_data(
        dataset, dry_run=False, raise_errors=False, collect_failed_rows=True
    )

    if result.has_errors():
        error_messages = ["Import errors!"]
        for error in result.base_errors:
            error_messages.append(repr(error.error))
        for line, errors in result.row_errors():
            for error in errors:
                error_messages.append(f"Line number: {line} - {repr(error.error)}")
        admin_instance.message_user(
            request, "\n".join(error_messages), level=messages.ERROR
        )
    else:
        success_message = (
            "Import finished: {} new, {} updated, {} deleted and {} skipped {}."
        ).format(
            result.totals[RowResult.IMPORT_TYPE_NEW],
            result.totals[RowResult.IMPORT_TYPE_UPDATE],
            result.totals[RowResult.IMPORT_TYPE_DELETE],
            result.totals[RowResult.IMPORT_TYPE_SKIP],
            resource._meta.model._meta.verbose_name_plural,
        )
        admin_instance.message_user(request, success_message, level=messages.SUCCESS)
    return redirect(".")


def download_source_file(admin_instance, request, url, file_name):
    try:
        response = requests.get(url, timeout=(5, 30))
        response.raise_for_status()
    except requests.Timeout:
        logger.exception("Source file download timed out", extra={"url": url})
        admin_instance.message_user(
            request,
            "Download failed: the source file server did not respond in time. Please try again.",
            level=messages.ERROR,
        )
        return redirect(".")
    except requests.HTTPError as e:
        status = e.response.status_code if e.response is not None else "unknown"
        logger.exception(
            "Source file download returned HTTP error",
            extra={"url": url, "status": status},
        )
        admin_instance.message_user(
            request,
            f"Download failed: source file returned HTTP {status}. "
            "Check that the file is published and the URL is correct.",
            level=messages.ERROR,
        )
        return redirect(".")
    except requests.RequestException:
        logger.exception("Source file download failed", extra={"url": url})
        admin_instance.message_user(
            request,
            "Download failed: could not reach the source file server. Please try again later.",
            level=messages.ERROR,
        )
        return redirect(".")

    return FileResponse(
        BytesIO(response.content), as_attachment=True, filename=file_name
    )
