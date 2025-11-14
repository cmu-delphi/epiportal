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
        "display_name": 'Hospital ("Facility")',
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
