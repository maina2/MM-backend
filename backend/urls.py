from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static


urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/users/', include('users.urls')), 
    path('api/', include('products.urls')), 
    path('api/', include('orders.urls')), 
    path('api/', include('delivery.urls')), 
    path('api/', include('payment.urls')), 
    
    ]

if settings.DEBUG:
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)