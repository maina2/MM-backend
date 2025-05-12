from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static


urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/users/', include('users.urls')), 
    path('api/', include('products.urls')), 
    path('api/orders/', include('orders.urls')), 
    path('api/delivery/', include('delivery.urls')), 
    path('api/payment/', include('payment.urls')), 
    
    ]+ static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)