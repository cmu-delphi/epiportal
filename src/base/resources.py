from import_export.resources import ModelResource

GEOGRAPHIC_GRANULARITY_MAPPING = {
    "nation": {
        "display_name": "National",
        "display_order_number": 1,
        "short_name": "National",
    },
    "hhs": {
        "display_name": "U.S. HHS Region",
        "display_order_number": 2,
        "short_name": "HHS",
    },
    "census-region": {
        "display_name": "U.S. Census Region",
        "display_order_number": 3,
        "short_name": "Census",
    },
    "region": {
        "display_name": "Other Subnational Region",
        "display_order_number": 4,
        "short_name": "Subnational",
    },
    "state": {
        "display_name": "State/ADM 1",
        "display_order_number": 5,
        "short_name": "ADM 1",
    },
    "county": {
        "display_name": "County/ADM 2",
        "display_order_number": 6,
        "short_name": "ADM 2",
    },
    "city": {
        "display_name": "Municipality/ADM 3",
        "display_order_number": 7,
        "short_name": "ADM 3",
    },
    "hsa_nci": {
        "display_name": "Health Service Area (HSA-NCI)",
        "display_order_number": 8,
        "short_name": "HSA-NCI",
    },
    "hrr": {
        "display_name": "Hospital Referral Region (HRR)",
        "display_order_number": 9,
        "short_name": "HRR",
    },
    "msa": {
        "display_name": "Metropolitan Statistical Area (MSA)",
        "display_order_number": 10,
        "short_name": "MSA",
    },
    "dma": {
        "display_name": "Designated Market Area (DMA)",
        "display_order_number": 11,
        "short_name": "DMA",
    },
    "other_substate_region": {
        "display_name": "Other Substate Region",
        "display_order_number": 12,
        "short_name": "Other Substate Region",
    },
    "FluSurv-Net site": {
        "display_name": "FluSurv-Net site (see documentation)",
        "display_order_number": 13,
        "short_name": "FluSurv-Net site",
    },
    "facility": {
        "display_name": 'Facility',
        "display_order_number": 14,
        "short_name": "Facility",
    },
    "lat_long": {
        "display_name": "Lat/Long",
        "display_order_number": 15,
        "short_name": "Lat/Long",
    },
    "N/A": {"display_name": "N/A", "display_order_number": 16, "short_name": "N/A"},
}


def get_geographic_mapping_by_name(name):
    """
    Get geographic granularity mapping by key or by display_name.

    First tries to get by key, then searches by display_name if not found.
    Returns a tuple (key, value) where key is the dictionary key and value
    is the mapping dict, or None if not found.
    """
    # First try to get by key
    mapping = GEOGRAPHIC_GRANULARITY_MAPPING.get(name)
    if mapping:
        return (name, mapping)

    # If not found, search by display_name
    for key, value in GEOGRAPHIC_GRANULARITY_MAPPING.items():
        if value.get("display_name") == name:
            return (key, value)

    return None


class CustomModelResource(ModelResource):
    # Columns read by the resource itself besides its fields' columns, such as
    # the ones deciding which rows are excluded.
    required_columns: tuple[str, ...] = ()

    def before_import(self, dataset, **kwargs):
        self.imported_rows_pks: list[int] = []
        self.deleted_count = 0
        # A missing column would read as empty in every row, which can exclude
        # every row and so delete everything; refuse the import instead.
        required = [field.column_name for field in self.get_import_fields()]
        required.extend(self.required_columns)
        headers = dataset.headers or []
        missing = [
            column for column in dict.fromkeys(required) if column not in headers
        ]
        if missing:
            raise ValueError(
                "Columns missing from the sheet: " + ", ".join(map(repr, missing))
            )

    def is_excluded(self, row) -> bool:
        """Rows to skip as if absent from the sheet, so their objects are deleted."""
        return False

    def skip_row(self, instance, original, row, import_validation_errors=None):
        if self.is_excluded(row):
            return True
        return super().skip_row(instance, original, row, import_validation_errors)

    def after_import_row(self, row, row_result, **kwargs):
        # A skipped row still carries the existing object's pk, so excluded
        # rows are left out here; rows skipped as unchanged are still kept.
        if not self.is_excluded(row):
            pk = getattr(row_result.instance, "pk", None) or row_result.object_id
            if pk:
                self.imported_rows_pks.append(pk)
        super().after_import_row(row, row_result, **kwargs)

    def after_import(self, dataset, result, **kwargs):
        if not kwargs.get("dry_run", False):
            stale = self._meta.model.objects.exclude(pk__in=self.imported_rows_pks)
            self.deleted_count = stale.count()
            stale.delete()
