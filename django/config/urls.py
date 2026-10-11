from django.conf import settings
from django.contrib import admin
from django.contrib.auth import views as auth_views
from django.http import HttpResponse
from django.urls import include, path
from django.views.static import serve
from oauth2_provider.urls import metadata_urlpatterns
from poc_oauth.views import MCPIntrospectionView

urlpatterns = [
    # PoC only: serve collected admin assets without a separate static container.
    path("static/<path:path>", serve, {"document_root": settings.STATIC_ROOT}),
    *(p for p in metadata_urlpatterns if p.name.startswith("oauth-server-metadata")),
    path("", lambda request: HttpResponse("Django OAuth PoC")),
    path("healthz", lambda request: HttpResponse("ok")),
    path("admin/", admin.site.urls),
    path("accounts/login/", auth_views.LoginView.as_view()),
    path("accounts/logout/", auth_views.LogoutView.as_view()),
    path("o/", include("oauth2_provider.urls", namespace="oauth2_provider")),
    path("mcp-oauth/introspect/", MCPIntrospectionView.as_view()),
]
