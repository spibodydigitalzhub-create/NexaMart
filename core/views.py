import requests, hmac, hashlib, json
from django.conf import settings
from django.contrib.auth import authenticate, login
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from django.shortcuts import render, redirect
from rest_framework import status, permissions
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.generics import ListAPIView, RetrieveAPIView
from rest_framework.parsers import MultiPartParser, FormParser
from .serializers import UserRegistrationSerializer, ProductSerializer, CategorySerializer
from .models import Product, Order, OrderItem, VendorProfile, Category

PAYSTACK_KEY = settings.PAYSTACK_SECRET_KEY

class IsVendor(permissions.BasePermission):
    def has_permission(self, request, view):
        return request.user and request.user.is_authenticated and request.user.role == 'vendor'

class IsApprovedVendor(permissions.BasePermission):
    def has_permission(self, request, view):
        if not (request.user and request.user.is_authenticated and request.user.role == 'vendor'): return False
        try: return request.user.vendor_profile.is_approved
        except VendorProfile.DoesNotExist: return False

class RegisterView(APIView):
    def post(self, request):
        serializer = UserRegistrationSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response({"message": "User registered successfully!"}, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class LoginView(APIView):
    def post(self, request):
        username = request.data.get('username')
        password = request.data.get('password')
        user = authenticate(request, username=username, password=password)
        if user is not None:
            login(request, user)
            return Response({"message": "Logged in successfully", "role": user.role})
        return Response({"error": "Invalid credentials"}, status=status.HTTP_400_BAD_REQUEST)

class CategoryListView(ListAPIView):
    serializer_class = CategorySerializer
    permission_classes = [permissions.AllowAny]
    queryset = Category.objects.all()

class ProductListView(ListAPIView):
    serializer_class = ProductSerializer
    permission_classes = [permissions.AllowAny]
    def get_queryset(self):
        queryset = Product.objects.filter(is_active=True, vendor__is_approved=True)
        category = self.request.query_params.get('category')
        search = self.request.query_params.get('search')
        if category: queryset = queryset.filter(category__name__iexact=category)
        if search: queryset = queryset.filter(name__icontains=search)
        return queryset

class ProductDetailView(RetrieveAPIView):
    serializer_class = ProductSerializer
    permission_classes = [permissions.AllowAny]
    queryset = Product.objects.filter(is_active=True, vendor__is_approved=True)

class MyOrdersView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    def get(self, request):
        orders = Order.objects.filter(buyer=request.user).order_by('-created_at')
        data = []
        for order in orders:
            items = [{"product": item.product.name, "quantity": item.quantity, "price": str(item.price)} for item in order.items.all()]
            data.append({"order_id": order.id, "total": str(order.total_amount), "status": order.status, "date": order.created_at, "items": items})
        return Response(data)

class CheckoutView(APIView):
    def post(self, request):
        items_data = request.data.get('items', [])
        buyer_email = request.data.get('email')

        if not items_data:
            return Response({"error": "Cart is empty"}, status=status.HTTP_400_BAD_REQUEST)

        total_amount_naira = 0
        vendor_splits = {} # { vendor_subaccount_code: amount_in_naira }
        order_items_to_create = []

        # 1. Validate items and calculate totals
        for item_data in items_data:
            try:
                product = Product.objects.get(id=item_data['product_id'], is_active=True)
            except Product.DoesNotExist:
                return Response({"error": f"Product {item_data['product_id']} not found"}, status=status.HTTP_404_NOT_FOUND)
            
            if product.stock < item_data.get('quantity', 1):
                return Response({"error": f"Not enough stock for {product.name}"}, status=status.HTTP_400_BAD_REQUEST)
            
            if not product.vendor.is_approved or not product.vendor.paystack_subaccount_code:
                return Response({"error": f"Vendor for {product.name} is not approved"}, status=status.HTTP_400_BAD_REQUEST)

            qty = item_data.get('quantity', 1)
            item_total = float(product.price) * qty
            total_amount_naira += item_total

            # Group by vendor
            vendor_code = product.vendor.paystack_subaccount_code
            vendor_splits[vendor_code] = vendor_splits.get(vendor_code, 0) + item_total
            
            order_items_to_create.append({'product': product, 'quantity': qty, 'price': product.price})

        # 2. Calculate Commission (5%)
        commission_percentage = 5
        total_amount_kobo = int(total_amount_naira * 100)
        transaction_charge = int(total_amount_kobo * (commission_percentage / 100))

        # 3. Prepare Paystack Subaccounts Payload
        subaccounts_payload = []
        for vendor_code, amount in vendor_splits.items():
            # Calculate this vendor's share in kobo
            vendor_share_kobo = int(amount * 100)
            subaccounts_payload.append({
                "subaccount": vendor_code,
                "share": vendor_share_kobo
            })

        url = "https://api.paystack.co/transaction/initialize"
        headers = {"Authorization": f"Bearer {PAYSTACK_KEY}", "Content-Type": "application/json"}
        callback_url = request.build_absolute_uri('/order-success/')
        
        payload = {
            "email": buyer_email,
            "amount": total_amount_kobo,
            "subaccounts": subaccounts_payload,
            "transaction_charge": transaction_charge,
            "bearer": "subaccount", # Paystack deducts fee from vendors proportionally
            "callback_url": callback_url
        }

        try:
            response = requests.post(url, headers=headers, json=payload)
            result = response.json()
            if result.get('status'):
                # 4. Save Order in Database
                order = Order.objects.create(
                    buyer=request.user if request.user.is_authenticated else None,
                    total_amount=total_amount_naira,
                    platform_fee=transaction_charge / 100,
                    vendor_payout=(total_amount_kobo - transaction_charge) / 100,
                    paystack_reference=result['data']['reference'],
                    status='pending'
                )
                for item_data in order_items_to_create:
                    OrderItem.objects.create(
                        order=order, 
                        product=item_data['product'], 
                        quantity=item_data['quantity'], 
                        price=item_data['price']
                    )
                return Response({"message": "Checkout initialized", "authorization_url": result['data']['authorization_url'], "reference": result['data']['reference']}, status=status.HTTP_200_OK)
            else:
                return Response({"error": result.get('message')}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class VendorAddProductView(APIView):
    permission_classes = [permissions.IsAuthenticated, IsApprovedVendor]
    parser_classes = [MultiPartParser, FormParser]
    def post(self, request):
        vendor_profile = request.user.vendor_profile
        product = Product.objects.create(vendor=vendor_profile, name=request.data.get('name'), description=request.data.get('description'), price=request.data.get('price'), stock=request.data.get('stock'), image=request.FILES.get('image'))
        return Response({"message": "Product added!", "product_id": product.id}, status=status.HTTP_201_CREATED)

class VendorMyProductsView(APIView):
    permission_classes = [permissions.IsAuthenticated, IsVendor]
    def get(self, request):
        vendor_profile = request.user.vendor_profile
        products = Product.objects.filter(vendor=vendor_profile)
        data = [{"id": p.id, "name": p.name, "price": str(p.price), "stock": p.stock, "image": p.image.url if p.image else None} for p in products]
        return Response(data)

class VendorOrdersView(APIView):
    permission_classes = [permissions.IsAuthenticated, IsVendor]
    def get(self, request):
        vendor_profile = request.user.vendor_profile
        order_items = OrderItem.objects.filter(product__vendor=vendor_profile).select_related('order', 'product')
        data = [{"order_id": item.order.id, "reference": item.order.paystack_reference, "customer": item.order.buyer.username if item.order.buyer else "Guest", "product": item.product.name, "quantity": item.quantity, "total": str(item.price * item.quantity), "status": item.order.status, "date": item.order.created_at.strftime('%Y-%m-%d %H:%M')} for item in order_items]
        return Response(data)

class UpdateOrderStatusView(APIView):
    permission_classes = [permissions.IsAuthenticated, IsVendor]
    def post(self, request):
        order_id = request.data.get('order_id')
        new_status = request.data.get('status')
        try:
            order = Order.objects.get(id=order_id)
            if OrderItem.objects.filter(order=order, product__vendor=request.user.vendor_profile).exists():
                order.status = new_status
                order.save()
                return Response({"message": "Order status updated successfully!"})
            else: return Response({"error": "You do not have products in this order."}, status=status.HTTP_403_FORBIDDEN)
        except Order.DoesNotExist: return Response({"error": "Order not found."}, status=status.HTTP_404_NOT_FOUND)

class VendorStorefrontView(ListAPIView):
    serializer_class = ProductSerializer
    permission_classes = [permissions.AllowAny]
    def get_queryset(self):
        vendor_id = self.kwargs['vendor_id']
        return Product.objects.filter(is_active=True, vendor__id=vendor_id, vendor__is_approved=True)

@method_decorator(csrf_exempt, name='dispatch')
class PaystackWebhookView(APIView):
    def post(self, request):
        paystack_signature = request.META.get('HTTP_X_PAYSTACK_SIGNATURE', '')
        secret = settings.PAYSTACK_SECRET_KEY
        body = request.body.decode('utf-8')
        computed_hash = hmac.new(secret.encode('utf-8'), body.encode('utf-8'), hashlib.sha512).hexdigest()
        if computed_hash != paystack_signature: return Response({"error": "Invalid signature"}, status=status.HTTP_401_UNAUTHORIZED)
        try: event = json.loads(body)
        except json.JSONDecodeError: return Response({"error": "Invalid JSON"}, status=status.HTTP_400_BAD_REQUEST)
        if event.get('event') == 'charge.success':
            reference = event['data']['reference']
            try:
                order = Order.objects.get(paystack_reference=reference)
                if order.status == 'pending':
                    order.status = 'paid'
                    order.save()
                    for item in order.items.all():
                        item.product.stock -= item.quantity
                        item.product.save()
            except Order.DoesNotExist: pass
        return Response({"message": "Webhook received"}, status=status.HTTP_200_OK)

def home_view(request): return render(request, 'home.html')
def checkout_view(request): return render(request, 'checkout.html')
def login_view(request): return render(request, 'login.html')
def register_view(request): return render(request, 'register.html')
def order_success_view(request): return render(request, 'order_success.html')
def vendor_dashboard_view(request):
    if not request.user.is_authenticated or request.user.role != 'vendor': return redirect('login')
    return render(request, 'vendor_dashboard.html')
def my_orders_view(request):
    if not request.user.is_authenticated: return redirect('login')
    return render(request, 'my_orders.html')
def vendor_orders_view(request):
    if not request.user.is_authenticated or request.user.role != 'vendor': return redirect('login')
    return render(request, 'vendor_orders.html')
def vendor_apply_view(request): return render(request, 'vendor_apply.html')
def product_detail_view(request, pk): return render(request, 'product_detail.html', {'product_id': pk})
def vendor_storefront_view(request, vendor_id): return render(request, 'vendor_storefront.html', {'vendor_id': vendor_id})
def cart_view(request): return render(request, 'cart.html')

# --- Vendor Analytics ---
class VendorStatsView(APIView):
    permission_classes = [permissions.IsAuthenticated, IsVendor]

    def get(self, request):
        vendor_profile = request.user.vendor_profile
        
        # Get all order items for this vendor's products
        order_items = OrderItem.objects.filter(product__vendor=vendor_profile).select_related('order')
        
        total_orders = order_items.values('order').distinct().count()
        total_products = Product.objects.filter(vendor=vendor_profile).count()
        
        # Calculate revenue (only from paid/delivered orders)
        revenue_items = order_items.filter(order__status__in=['paid', 'shipped', 'delivered'])
        total_revenue = sum(item.price * item.quantity for item in revenue_items)

        return Response({
            "total_orders": total_orders,
            "total_revenue": str(total_revenue),
            "total_products": total_products
        })

# --- Admin Analytics ---
from django.db.models import Sum

class IsAdmin(permissions.BasePermission):
    def has_permission(self, request, view):
        return request.user and request.user.is_authenticated and request.user.role == 'admin'

class AdminStatsView(APIView):
    permission_classes = [permissions.IsAuthenticated, IsAdmin]

    def get(self, request):
        # Calculate total platform revenue (your 5% cut) from successful orders
        total_revenue = Order.objects.filter(status__in=['paid', 'shipped', 'delivered']).aggregate(Sum('platform_fee'))['platform_fee__sum'] or 0
        
        total_vendors = VendorProfile.objects.filter(is_approved=True).count()
        total_customers = CustomUser.objects.filter(role='customer').count()
        total_orders = Order.objects.count()

        return Response({
            "total_revenue": str(total_revenue),
            "total_vendors": total_vendors,
            "total_customers": total_customers,
            "total_orders": total_orders
        })

def admin_dashboard_view(request):
    if not request.user.is_authenticated or request.user.role != 'admin':
        return redirect('login')
    return render(request, 'admin_dashboard.html')

# --- Reviews & Ratings ---
from .serializers import ReviewSerializer

class ReviewListView(ListAPIView):
    serializer_class = ReviewSerializer
    permission_classes = [permissions.AllowAny]

    def get_queryset(self):
        product_id = self.kwargs['product_id']
        return Review.objects.filter(product__id=product_id).order_by('-created_at')

class CreateReviewView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, product_id):
        try:
            product = Product.objects.get(id=product_id)
        except Product.DoesNotExist:
            return Response({"error": "Product not found"}, status=status.HTTP_404_NOT_FOUND)

        # Check if user already reviewed
        if Review.objects.filter(product=product, user=request.user).exists():
            return Response({"error": "You have already reviewed this product."}, status=status.HTTP_400_BAD_REQUEST)

        rating = request.data.get('rating')
        comment = request.data.get('comment', '')

        if not rating or not (1 <= int(rating) <= 5):
            return Response({"error": "Rating must be between 1 and 5."}, status=status.HTTP_400_BAD_REQUEST)

        review = Review.objects.create(
            product=product,
            user=request.user,
            rating=int(rating),
            comment=comment
        )
        serializer = ReviewSerializer(review)
        return Response(serializer.data, status=status.HTTP_201_CREATED)
