from django.urls import path
from . import views

urlpatterns = [
    path('', views.index, name='dashboard'),
    path('patterns/', views.pattern_list, name='pattern_list'),
    path('patterns/upload/', views.pattern_upload, name='pattern_upload'),
    path('patterns/batch/', views.pattern_batch, name='pattern_batch'),
    path('templates/', views.template_list, name='template_list'),
    path('templates/upload/', views.template_upload, name='template_upload'),
    path('products/', views.product_list, name='product_list'),
    path('products/export/', views.product_export, name='product_export'),
]
