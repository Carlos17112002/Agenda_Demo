from django.http import Http404
from django.shortcuts import render
from django.urls import reverse
from django.views import View
from rest_framework.exceptions import NotFound

from .public import company_payload, public_company


class PublicBookingPageView(View):
    template_name = "public/booking.html"

    def get(self, request, slug, code=None):
        try:
            company = public_company(slug)
        except (Http404, NotFound):
            raise Http404
        payload = company_payload(company, request)
        context = {
            "branding": payload["branding"],
            "payload": payload,
            "initial_code": code or "",
            "company_url": reverse("public-company", args=[company.slug]),
            "availability_url": reverse("public-availability", args=[company.slug]),
            "bookings_url": reverse("public-booking-create", args=[company.slug]),
            "detail_base": reverse("public-booking-detail", args=[company.slug, "CODE"]),
            "cancel_base": reverse("public-booking-cancel", args=[company.slug, "CODE"]),
        }
        response = render(request, self.template_name, context)
        response["Cache-Control"] = "no-store"
        return response
