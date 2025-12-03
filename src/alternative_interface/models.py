from django.db import models


class ExpressViewIndicator(models.Model):
    menu_item = models.CharField(
        verbose_name="Menu Item",
        max_length=255,
    )
    indicator = models.ForeignKey(
        "indicators.Indicator",
        verbose_name="Indicator",
        on_delete=models.PROTECT,
    )
    display_name = models.CharField(
        verbose_name="Display Name",
        max_length=255,
    )

    class Meta:
        verbose_name = "Express View Indicator"
        verbose_name_plural = "Express View Indicators"
        ordering = ["menu_item", "indicator"]
        indexes = [
            models.Index(
                fields=["menu_item", "indicator"],
                name="expr_view_ind_menu_idx",
            ),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["menu_item", "indicator"],
                name="uniq_expr_view_menu_ind",
            ),
        ]

    def __str__(self):
        return self.display_name
