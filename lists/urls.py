from django.urls import path

from . import views

urlpatterns = [
    path('', views.index, name='index'),
    path('import/', views.restaurant_nominatim, name='restaurant_nominatim'),
    path('restaurants/', views.restaurant_index, name='restaurant_index'),
    path('list/', views.restaurantlist_index, name='restaurantlist_index'),
    path('list/my/', views.user_restaurantlist_index, name='user_restaurantlist_index'),
    path('list/create/', views.restaurantlist_create, name='restaurantlist_create'),
    path('list/<int:list_id>/', views.restaurantlist_detail, name='restaurantlist_detail'),
    path('list/<int:list_id>/edit/', views.restaurantlist_edit, name='restaurantlist_edit'),
    path('list/<int:list_id>/update/', views.restaurantlist_update, name='restaurantlist_update'),
    path('list/<int:list_id>/delete/', views.restaurantlist_delete, name='restaurantlist_delete'),
    path('list/<int:list_id>/follow/', views.toggle_list_follow, name='toggle_list_follow'),
    path('listitem/create/', views.restaurantlistitem_create, name='restaurantlistitem_create'),
    path('listitem/<int:item_id>/move-up/', views.move_item_up, name='move_item_up'),
    path('listitem/<int:item_id>/move-down/', views.move_item_down, name='move_item_down'),
    path('listitem/<int:item_id>/delete/', views.restaurantlistitem_delete, name='restaurantlistitem_delete'),
    path('restaurant/<int:restaurant_id>/', views.restaurant_detail, name='restaurant_detail'),
    path('restaurant/<int:restaurant_id>/add-image/', views.restaurant_image_add, name='restaurant_image_add'),
    path('profile/<int:user_id>/', views.profile, name='profile'),
    path('profile/<int:user_id>/following/', views.user_following_lists, name='user_following_lists'),
    path('list/<int:list_id>/followers/', views.list_followers, name='list_followers'),
    path('api/restaurant/search/', views.restaurant_search_api, name='restaurant_search_api'),
]