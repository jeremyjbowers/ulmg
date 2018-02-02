from django.contrib import admin
from django.urls import include, path
import nested_admin

urlpatterns = [
    path('nested_admin/', include('nested_admin.urls')),
    path('admin/', admin.site.urls),
]