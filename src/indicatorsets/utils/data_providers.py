"""Parsing and grouping of OriginalDataProvider filter values."""

from indicatorsets.models import OriginalDataProvider


def parse_original_data_provider_ids(query_dict):
    raw_values = []

    for odp_value in query_dict.getlist("odp"):
        raw_values.extend(v.strip() for v in odp_value.split(",") if v.strip())

    raw_values.extend(query_dict.getlist("original_data_provider"))

    ids = []
    names = []
    for value in raw_values:
        if str(value).isdigit():
            ids.append(int(value))
        elif value:
            names.append(value)

    if names:
        ids.extend(
            OriginalDataProvider.objects.filter(name__in=names).values_list(
                "id", flat=True
            )
        )

    # dedupe, preserve order
    seen = set()
    return [i for i in ids if not (i in seen or seen.add(i))]


def sort_data_providers(providers):
    """Sort providers alphabetically, with names containing 'other' at the end."""
    sorted_providers = sorted(providers, key=lambda p: p.name.lower())
    tail = [
        provider for provider in sorted_providers if "other" in provider.name.lower()
    ]
    head = [
        provider
        for provider in sorted_providers
        if "other" not in provider.name.lower()
    ]
    return head + tail


def get_grouped_original_data_provider_choices():
    providers = (
        OriginalDataProvider.objects.filter(indicator_sets__isnull=False)
        .distinct()
        .order_by("display_order", "name")
    )
    provider_list = list(providers)
    return {
        "main": sort_data_providers(
            [p for p in provider_list if p.group == "individual"]
        ),
        "groups": [
            {
                "label": "U.S. Government",
                "providers": sort_data_providers(
                    [p for p in provider_list if p.group == "us_government"]
                ),
            },
            {
                "label": "U.S. States",
                "providers": sort_data_providers(
                    [p for p in provider_list if p.group == "us_states"]
                ),
            },
        ],
        "all": sort_data_providers(provider_list),
    }
