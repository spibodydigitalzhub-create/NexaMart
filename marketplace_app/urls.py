from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from core.views import (
    home_view, checkout_view, login_view, register_view, order_success_view, 
    vendor_dashboard_view, my_orders_view, vendor_orders_view, vendor_apply_view,
    product_detail_view, vendor_storefront_view, cart_view, admin_dashboard_view
)

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/', include('core.urls')),
    path('', home_view, name='home'),
    path('checkout/', checkout_view, name='checkout'),
    path('login/', login_view, name='login'),
    path('register/', register_view, name='register'),
    path('order-success/', order_success_view, name='order-success'),
    path('my-orders/', my_orders_view, name='my-orders'),
    path('vendor/dashboard/', vendor_dashboard_view, name='vendor-dashboard'),
    path('vendor/orders/', vendor_orders_view, name='vendor-orders'),
    path('become-a-vendor/', vendor_apply_view, name='vendor-apply'),
    path('product/<int:pk>/', product_detail_view, name='product-detail-page'),
    path('store/<int:vendor_id>/', vendor_storefront_view, name='vendor-storefront'),
    path('cart/', cart_view, name='cart'),
    path('admin-dashboard/', admin_dashboard_view, name='admin-dashboard'),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
