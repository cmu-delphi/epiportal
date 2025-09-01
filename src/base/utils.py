from io import BytesIO, TextIOWrapper

import requests
from django.contrib import messages
from django.shortcuts import redirect
from django.utils.module_loading import import_string
from import_export.results import RowResult


def import_data(admin_instance, request, resource_class, spreadsheet_url):
    resource = resource_class()
    format_class = import_string("import_export.formats.base_formats.CSV")

    response = requests.get(spreadsheet_url)
    response.raise_for_status()

    csvfile = TextIOWrapper(BytesIO(response.content), encoding="utf-8")

    dataset = format_class().create_dataset(csvfile.read())

    result = resource.import_data(dataset, dry_run=False, raise_errors=True)

    if result.has_errors():
        error_messages = ["Import errors!"]
        for error in result.base_errors:
            error_messages.append(repr(error.error))
        for line, errors in result.row_errors():
            for error in errors:
                error_messages.append(f"Line number: {line} - {repr(error.error)}")
        admin_instance.message_user(request, "\n".join(error_messages), level=messages.ERROR)
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
