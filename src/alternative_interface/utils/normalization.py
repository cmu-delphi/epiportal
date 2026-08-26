"""Scaling chart series to a common 0-100 range.

Epidata values arrive with None for missing points and occasionally NaN or
infinity; every helper here treats all three as "no value" and emits None.
"""


def _is_finite_number(value):
    """True when value is a real number that can be plotted."""
    if value is None:
        return False
    if isinstance(value, float) and (
        value != value or value in (float("inf"), float("-inf"))
    ):
        return False
    return True


def _values_in_view(data, day_labels, view_start, view_end):
    """Finite values whose day label falls inside the initial view window.

    Returns None when the window cannot be applied -- no labels, no bounds, or
    a length mismatch with ``data`` -- which tells callers to fall back to the
    whole series.
    """
    if not (day_labels and view_start and view_end):
        return None
    if len(day_labels) != len(data):
        return None
    return [
        value
        for value, label in zip(data, day_labels)
        if view_start <= label <= view_end and _is_finite_number(value)
    ]


def _scale(data, factor):
    """Multiply every finite value by factor, emitting None for the rest."""
    return [value * factor if _is_finite_number(value) else None for value in data]


def group_maximum(series, day_labels=None, view_start=None, view_end=None):
    """Largest finite value across several series, preferring the view window.

    Falls back to the whole series only when the window yields nothing at all.

    Returns:
        A ``(maximum, found)`` pair. ``found`` is False when no series holds a
        positive finite value -- including an all-negative group, since the
        maximum is only ever raised above zero.
    """
    maximum = 0
    found = False
    for data in series:
        in_view = _values_in_view(data, day_labels, view_start, view_end)
        if in_view:
            current = max(in_view)
            if current > maximum:
                maximum, found = current, True
    if found:
        return maximum, True
    for data in series:
        finite = [value for value in data if _is_finite_number(value)]
        if finite:
            current = max(finite)
            if current > maximum:
                maximum, found = current, True
    return maximum, found


def normalize_dataset(
    data,
    day_labels=None,
    initial_view_start=None,
    initial_view_end=None,
    max_value=None,
):
    """Scale a series so its reference maximum becomes 100.

    Without ``max_value`` the reference is the series' own maximum, preferring
    values inside the initial view window and falling back to the whole series.

    Args:
        max_value: Scale against this maximum instead of deriving one. Used for
            group normalization, where several series share one scale so their
            relative heights stay comparable.
    """
    if not data:
        return data

    if max_value is not None:
        # A non-positive group maximum means nothing usable was found, so
        # magnitudes are left alone -- but the series is still rebuilt so
        # non-finite values become None.
        return _scale(data, 100.0 / max_value if max_value > 0 else 1.0)

    in_view = _values_in_view(data, day_labels, initial_view_start, initial_view_end)
    if in_view:
        maximum = max(in_view)
        if maximum > 0:
            return _scale(data, 100.0 / maximum)

    finite = [value for value in data if _is_finite_number(value)]
    if not finite:
        return data
    maximum = max(finite)
    if maximum <= 0:
        return data
    return _scale(data, 100.0 / maximum)
