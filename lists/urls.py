from django.urls import path

from . import views

urlpatterns = [
    path('', views.index, name='index'),
    path('search/', views.search_restaurants, name='search_restaurants'),
    path('restaurants/', views.restaurant_index, name='restaurant_index'),
    path('lists/', views.restaurantlist_index, name='restaurantlist_index'),
    path('lists/create/', views.create_restaurantlist, name='create_restaurantlist'),
    path('lists/<int:list_id>/', views.restaurantlist_detail, name='restaurantlist_detail'),
    path('lists/add-restaurant/', views.create_restaurantlistitem, name='create_restaurantlistitem'),
    path('lists/item/<int:item_id>/move-up/', views.move_item_up, name='move_item_up'),
    path('lists/item/<int:item_id>/move-down/', views.move_item_down, name='move_item_down'),
    path('restaurant/<int:restaurant_id>/', views.restaurant_detail, name='restaurant_detail'),
]