from django.conf import settings


def client_ip(request):
    if request is None:
        return ""
    if getattr(settings, "TRUST_PROXY_HEADERS", False):
        forwarded = request.META.get("HTTP_X_FORWARDED_FOR", "")
        hops = [hop.strip() for hop in forwarded.split(",") if hop.strip()]
        if hops:
            trusted = max(int(getattr(settings, "TRUSTED_PROXY_COUNT", 1)), 0)
            index = max(len(hops) - trusted - 1, 0)
            return hops[index]
    return request.META.get("REMOTE_ADDR", "")
