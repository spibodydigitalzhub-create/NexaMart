from rest_framework import serializers
from django.contrib.auth import get_user_model
from django.db.models import Avg
from .models import VendorProfile, Product, Category, Review

User = get_user_model()

class UserRegistrationSerializer(serializers.ModelSerializer):
    store_name = serializers.CharField(required=False, allow_blank=True)
    class Meta:
        model = User
        fields = ['username', 'password', 'email', 'phone_number', 'role', 'store_name']
        extra_kwargs = {'password': {'write_only': True}}
    def create(self, validated_data):
        store_name = validated_data.pop('store_name', None)
        role = validated_data.get('role')
        user = User.objects.create_user(**validated_data)
        if role == 'vendor' and store_name:
            VendorProfile.objects.create(user=user, store_name=store_name)
        return user

class CategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = ['id', 'name', 'icon']

class ReviewSerializer(serializers.ModelSerializer):
    user_name = serializers.CharField(source='user.username', read_only=True)
    class Meta:
        model = Review
        fields = ['id', 'user_name', 'rating', 'comment', 'created_at']

class ProductSerializer(serializers.ModelSerializer):
    vendor_name = serializers.CharField(source='vendor.store_name', read_only=True)
    category_name = serializers.CharField(source='category.name', read_only=True)
    average_rating = serializers.SerializerMethodField()
    review_count = serializers.SerializerMethodField()
    
    class Meta:
        model = Product
        fields = ['id', 'name', 'description', 'price', 'stock', 'image', 'vendor_name', 'category_name', 'average_rating', 'review_count', 'created_at']

    def get_average_rating(self, obj):
        avg = obj.reviews.aggregate(Avg('rating'))['rating__avg']
        return round(avg, 1) if avg else 0.0

    def get_review_count(self, obj):
        return obj.reviews.count()
