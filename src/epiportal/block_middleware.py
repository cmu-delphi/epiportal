import ipaddress
from django.http import HttpResponseForbidden
from epiportal.utils import get_client_ip


class BlockIPRangeMiddleware:
    BLOCKED_NETWORKS = [
        ipaddress.ip_network("43.173.0.0/16"),
        ipaddress.ip_network("43.163.0.0/16"),
        ipaddress.ip_network("216.73.216.0/24"),
    ]

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        client_ip = get_client_ip(request)
        if any(
            ipaddress.ip_address(client_ip) in network
            for network in self.BLOCKED_NETWORKS
        ):
            return HttpResponseForbidden(
                "Access denied. Please contact us at support@delphi.cmu.edu if you believe this is an error."
            )
        return self.get_response(request)
