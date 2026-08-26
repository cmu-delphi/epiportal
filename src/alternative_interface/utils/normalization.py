"""Scaling chart series to a common 0-100 range."""


def normalize_dataset(
    data, day_labels=None, initial_view_start=None, initial_view_end=None
):
    """
    Scale a dataset so that its highest value during the displayed 2 years is set to 100.
    Multiplies each value by a constant (100 / max_value_in_range).
    Preserves None values for missing data.
    """
    if not data:
        return data

    # If we have the initial view range, scale based on max value in that range
    if (
        day_labels
        and initial_view_start
        and initial_view_end
        and len(day_labels) == len(data)
    ):
        # Find indices that fall within the initial view range (2 years)
        view_indices = []
        for i, day_label in enumerate(day_labels):
            if initial_view_start <= day_label <= initial_view_end:
                view_indices.append(i)

        # Find max value only in the view range
        view_values = [
            data[i]
            for i in view_indices
            if i < len(data)
            and data[i] is not None
            and not (
                isinstance(data[i], float)
                and (data[i] != data[i] or data[i] in (float("inf"), float("-inf")))
            )
        ]

        if view_values:
            max_val_in_range = max(view_values)
            if max_val_in_range > 0:
                # Scale factor: multiply by (100 / max_value_in_range)
                scale_factor = 100.0 / max_val_in_range

                # Scale all values in the dataset
                normalized = []
                for value in data:
                    if value is None:
                        normalized.append(None)
                    elif isinstance(value, float) and (
                        value != value or value in (float("inf"), float("-inf"))
                    ):
                        normalized.append(None)
                    else:
                        normalized.append(value * scale_factor)
                return normalized

    # Fallback: if no view range provided, scale based on max value in entire dataset
    numeric_values = [
        v
        for v in data
        if v is not None
        and not (
            isinstance(v, float) and (v != v or v in (float("inf"), float("-inf")))
        )
    ]

    if not numeric_values:
        return data  # Return as-is if no valid numeric values

    max_val = max(numeric_values)
    if max_val <= 0:
        return data  # Return as-is if max is 0 or negative

    # Scale so max value = 100
    scale_factor = 100.0 / max_val

    # Scale each value
    normalized = []
    for value in data:
        if value is None:
            normalized.append(None)
        elif isinstance(value, float) and (
            value != value or value in (float("inf"), float("-inf"))
        ):
            normalized.append(None)
        else:
            normalized.append(value * scale_factor)

    return normalized
