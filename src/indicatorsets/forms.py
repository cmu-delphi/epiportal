from django import forms
from django.db.models import Case, When, IntegerField

from base.models import Pathogen, Geography, SeverityPyramidRung
from indicatorsets.models import IndicatorSet
from indicatorsets.utils import get_original_data_provider_choices


class IndicatorSetFilterForm(forms.ModelForm):

    pathogens = forms.ModelMultipleChoiceField(
        queryset=Pathogen.objects.filter(
            indicator_sets__isnull=False
        ).annotate(
            sort_priority=Case(
                When(name__iexact="pathogen independent", then=1),
                default=0,
                output_field=IntegerField(),
            )
        ).order_by("sort_priority", "name").distinct(),
        widget=forms.CheckboxSelectMultiple(),
    )

    geographic_levels = forms.ModelMultipleChoiceField(
        queryset=Geography.objects.filter(
            indicator_sets__isnull=False
        ).distinct().order_by("display_order_number"),
        widget=forms.CheckboxSelectMultiple(),
    )
    severity_pyramid_rungs = forms.ModelMultipleChoiceField(
        queryset=SeverityPyramidRung.objects.filter(
            indicator_sets__isnull=False
        ).distinct().order_by("display_order_number"),
        widget=forms.CheckboxSelectMultiple(),
    )

    original_data_provider = forms.MultipleChoiceField(
        choices=get_original_data_provider_choices,
        widget=forms.CheckboxSelectMultiple(),
        required=False,
    )

    temporal_granularity = forms.ChoiceField(
        choices=[
            ("Annually", "Annually"),
            ("Monthly", "Monthly"),
            ("Weekly", "Weekly"),
            ("Daily", "Daily"),
            ("Hourly", "Hourly"),
            ("Other", "Other"),
        ],
        widget=forms.CheckboxSelectMultiple(),
    )

    temporal_scope_end = forms.ChoiceField(
        choices=[
            ("Ongoing", "Ongoing Surveillance Only"),
        ],
        required=False,
        widget=forms.CheckboxSelectMultiple(),
    )

    hosted_by_delphi = forms.BooleanField(
        label="Delphi-hosted Only",
        required=False,
        widget=forms.CheckboxInput(attrs={"value": "on"}),
    )

    location_search = forms.CharField(
        label=("Location Search"),
        widget=forms.TextInput(),
    )

    class Meta:
        model = IndicatorSet
        fields: list[str] = [
            "pathogens",
            "geographic_levels",
            "severity_pyramid_rungs",
            "original_data_provider",
            "temporal_granularity",
            "temporal_scope_end",
            "hosted_by_delphi",
        ]

    def __init__(self, *args, **kwargs) -> None:
        """
        Initialize the form.
        """
        super().__init__(*args, **kwargs)

        # Set required attribute to False and disable helptext for all fields
        for field_name, field in self.fields.items():
            field.required = False
            field.help_text = ""
            # Preserve label for hosted_by_delphi checkbox
            if field_name != "hosted_by_delphi":
                field.label = ""
            else:
                field.label = "Delphi-hosted Only"
