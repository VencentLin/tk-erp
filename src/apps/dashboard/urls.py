from django.urls import path
from . import views

urlpatterns = [
    path('', views.index, name='dashboard'),
    path('settings/', views.settings_page, name='settings_page'),

    # Country & Store
    path('countries/', views.country_list, name='country_list'),
    path('countries/save/', views.country_save, name='country_save'),
    path('countries/<int:cid>/delete/', views.country_delete, name='country_delete'),
    path('stores/save/', views.store_save, name='store_save'),
    path('stores/<int:sid>/delete/', views.store_delete, name='store_delete'),

    # Users
    path('users/', views.user_list, name='user_list'),
    path('users/save/', views.user_save, name='user_save'),
    path('users/<int:uid>/delete/', views.user_delete, name='user_delete'),

    # Categories
    path('categories/', views.category_list, name='category_list'),
    path('categories/upload/', views.category_upload, name='category_upload'),
    path('categories/task/<int:task_id>/', views.category_task_status, name='category_task_status'),
    path('categories/<int:cid>/edit/', views.category_edit, name='category_edit'),
    path('categories/<int:cid>/delete/', views.category_delete, name='category_delete'),
    path('categories/batch-delete/', views.category_batch_delete, name='category_batch_delete'),
    path('categories/batch-hard-delete/', views.category_batch_hard_delete, name='category_batch_hard_delete'),
    path('categories/batch-regenerate/', views.category_batch_regenerate, name='category_batch_regenerate'),
    path('categories/<int:cid>/hard-delete/', views.category_hard_delete, name='category_hard_delete'),

    # Prompt Presets (直接 .md 提示词)
    path('presets/', views.preset_list, name='preset_list'),
    path('presets/upload/', views.preset_upload, name='preset_upload'),
    path('presets/<int:pid>/edit/', views.preset_edit, name='preset_edit'),
    path('presets/<int:pid>/delete/', views.preset_delete, name='preset_delete'),
    path('presets/batch-delete/', views.preset_batch_delete, name='preset_batch_delete'),
    path('presets/classify/', views.preset_classify, name='preset_classify'),

    # Templates
    path('templates/', views.template_list, name='template_list'),
    path('templates/upload/', views.template_upload, name='template_upload'),
    path('templates/<int:tid>/edit/', views.template_edit, name='template_edit'),
    path('templates/<int:tid>/delete/', views.template_delete, name='template_delete'),

    # Products
    path('products/', views.product_list, name='product_list'),
    path('products/create/', views.product_create, name='product_create'),
    path('products/export/', views.product_export, name='product_export'),
    path('products/generate-all/', views.product_generate_all, name='product_generate_all'),
    path('products/batch-delete/', views.product_batch_delete, name='product_batch_delete'),
    path('products/batch-regenerate/', views.product_batch_regenerate, name='product_batch_regenerate'),
    path('products/<int:pid>/edit/', views.product_edit, name='product_edit'),
    path('products/<int:pid>/delete/', views.product_delete, name='product_delete'),
    path('products/<int:pid>/regenerate/', views.product_regenerate, name='product_regenerate'),

    # Image Assets
    path('image-assets/', views.image_asset_list, name='image_asset_list'),
    path('image-assets/upload/', views.image_asset_upload, name='image_asset_upload'),
    path('image-assets/create-products/', views.image_asset_create_products, name='image_asset_create_products'),
    path('image-assets/<int:aid>/delete/', views.image_asset_delete, name='image_asset_delete'),
    path('image-assets/batch-delete/', views.image_asset_batch_delete, name='image_asset_batch_delete'),
]
