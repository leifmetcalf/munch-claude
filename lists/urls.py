from django.urls import path

from . import views

urlpatterns = [
    path('', views.index, name='index'),
    path('search/', views.restaurant_nominatim, name='restaurant_nominatim'),
    path('restaurants/', views.restaurant_index, name='restaurant_index'),
    path('lists/', views.restaurantlist_index, name='restaurantlist_index'),
    path('lists/create/', views.restaurantlist_create, name='restaurantlist_create'),
    path('lists/<int:list_id>/', views.restaurantlist_detail, name='restaurantlist_detail'),
    path('lists/<int:list_id>/edit/', views.restaurantlist_edit, name='restaurantlist_edit'),
    path('lists/<int:list_id>/add-restaurant/', views.restaurantlistitem_create, name='restaurantlistitem_create'),
    path('lists/item/<int:item_id>/move-up/', views.move_item_up, name='move_item_up'),
    path('lists/item/<int:item_id>/move-down/', views.move_item_down, name='move_item_down'),
    path('lists/item/<int:item_id>/delete/', views.restaurantlistitem_delete, name='restaurantlistitem_delete'),
    path('restaurant/<int:restaurant_id>/', views.restaurant_detail, name='restaurant_detail'),
    path('restaurant/<int:restaurant_id>/add-to-list/', views.restaurant_add_to_list, name='restaurant_add_to_list'),
    path('restaurant/<int:restaurant_id>/add-image/', views.restaurant_image_add, name='restaurant_image_add'),
]