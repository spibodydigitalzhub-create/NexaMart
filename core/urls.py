from django.urls import path
from .views import (
    RegisterView, LoginView, CheckoutView, PaystackWebhookView,
    VendorAddProductView, VendorMyProductsView, VendorOrdersView, UpdateOrderStatusView,
    ProductListView, ProductDetailView, MyOrdersView, CategoryListView, VendorStorefrontView, VendorStatsView, AdminStatsView,
    ReviewListView, CreateReviewView
)

urlpatterns = [
    path('register/', RegisterView.as_view(), name='register'),
    path('login/', LoginView.as_view(), name='login'),
    path('categories/', CategoryListView.as_view(), name='category-list'),
    path('products/', ProductListView.as_view(), name='product-list'),
    path('products/<int:pk>/', ProductDetailView.as_view(), name='product-detail'),
    path('products/<int:product_id>/reviews/', ReviewListView.as_view(), name='product-reviews'),
    path('products/<int:product_id>/add-review/', CreateReviewView.as_view(), name='add-review'),
    path('my-orders/', MyOrdersView.as_view(), name='my-orders'),
    path('checkout/', CheckoutView.as_view(), name='checkout'),
    path('webhook/paystack/', PaystackWebhookView.as_view(), name='paystack-webhook'),
    path('vendor/add-product/', VendorAddProductView.as_view(), name='vendor-add-product'),
    path('vendor/my-products/', VendorMyProductsView.as_view(), name='vendor-my-products'),
    path('vendor/orders/', VendorOrdersView.as_view(), name='vendor-orders'),
    path('vendor/update-order/', UpdateOrderStatusView.as_view(), name='update-order-status'),
    path('vendor/storefront/<int:vendor_id>/', VendorStorefrontView.as_view(), name='api-vendor-storefront'),
    path('vendor/stats/', VendorStatsView.as_view(), name='vendor-stats'),
    path('admin/stats/', AdminStatsView.as_view(), name='admin-stats'),
]
