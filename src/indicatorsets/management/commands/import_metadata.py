"""Import every tab of the metadata sheet, atomically.

Same run as the admin's "Import all metadata from spreadsheet" button, for use
from a shell or a scheduled job. Any failure rolls the whole import back and
exits non-zero.
"""

from django.core.management.base import BaseCommand, CommandError

from indicatorsets.metadata_import import (
    MetadataImportError,
    format_results,
    run_metadata_import,
)


class Command(BaseCommand):
    help = "Import all tabs of the metadata sheet in one atomic run."

    def handle(self, *args, **options):
        try:
            results = run_metadata_import()
        except MetadataImportError as e:
            raise CommandError(str(e)) from e

        for line in format_results(results):
            self.stdout.write(line)
        for result in results:
            for warning in result.warnings:
                self.stdout.write(self.style.WARNING(f"{result.tab}: {warning}"))
