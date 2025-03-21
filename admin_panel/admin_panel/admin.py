from django.contrib import admin


class BallsdexAdminSite(admin.AdminSite):
    site_header = "DexAdmin"  # TODO: use configured bot name
    site_title = "Dex Panel"
    site_url = None
    final_catch_all_view = False
