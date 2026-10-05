from base.models import Banner


def banners(request):
    """Add the banners currently due to every rendered page."""
    return {"site_banners": Banner.objects.current()}
