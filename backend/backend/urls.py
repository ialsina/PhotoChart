"""
URL configuration for backend project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""

from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from rest_framework.routers import DefaultRouter
from photograph.views import PhotographViewSet, PhotoPathViewSet
from catalog.views import (
    HashViewSet,
    DirectoryViewSet,
    DirKindViewSet,
    LocationViewSet,
    TimeLocViewSet,
)

# Create a router and register viewsets
router = DefaultRouter()
router.register(r"photographs", PhotographViewSet, basename="photograph")
router.register(r"photo-paths", PhotoPathViewSet, basename="photopath")
router.register(r"hashes", HashViewSet, basename="hash")
router.register(r"directories", DirectoryViewSet, basename="directory")
router.register(r"dir-kinds", DirKindViewSet, basename="dirkind")
router.register(r"locations", LocationViewSet, basename="location")
router.register(r"time-locs", TimeLocViewSet, basename="timeloc")

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/", include(router.urls)),
]

# Serve media files in development
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
