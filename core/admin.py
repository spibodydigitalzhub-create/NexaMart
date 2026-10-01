import requests
from django.contrib import admin
from django.conf import settings
from .models import CustomUser, VendorProfile, Product, Order, OrderItem, Category, Review

PAYSTACK_KEY = settings.PAYSTACK_SECRET_KEY

@admin.register(CustomUser)
class CustomUserAdmin(admin.ModelAdmin):
    list_display = ('username', 'email', 'role', 'is_active')
    list_filter = ('role', 'is_active')

@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'icon')
    search_fields = ('name',)

@admin.register(Review)
class ReviewAdmin(admin.ModelAdmin):
    list_display = ('product', 'user', 'rating', 'created_at')
    list_filter = ('rating',)

@admin.register(VendorProfile)
class VendorProfileAdmin(admin.ModelAdmin):
    list_display = ('store_name', 'user', 'is_approved', 'paystack_subaccount_code')
    list_filter = ('is_approved',)

    def save_model(self, request, obj, form, change):
        if obj.is_approved and not obj.paystack_subaccount_code:
            url = "https://api.paystack.co/subaccount"
            headers = {
                "Authorization": f"Bearer {PAYSTACK_KEY}",
                "Content-Type": "application/json"
            }
            data = {
                "business_name": obj.store_name,
                "settlement_bank": obj.settlement_bank,
                "account_number": obj.account_number,
                "percentage_charge": 5
            }
            try:
                response = requests.post(url, headers=headers, json=data)
                result = response.json()
                if result.get('status'):
                    obj.paystack_subaccount_code = result['data']['subaccount_code']
                    self.message_user(request, f"Success! Paystack Subaccount created: {obj.paystack_subaccount_code}")
                else:
                    self.message_user(request, f"Paystack Error: {result.get('message')}", level='error')
            except Exception as e:
                self.message_user(request, f"Connection Error: {str(e)}", level='error')

        super().save_model(request, obj, form, change)

@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ('name', 'vendor', 'price', 'stock', 'is_active')

@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ('buyer', 'total_amount', 'platform_fee', 'status', 'created_at')

@admin.register(OrderItem)
class OrderItemAdmin(admin.ModelAdmin):
    list_display = ('order', 'product', 'quantity', 'price')
