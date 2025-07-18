import json
import urllib.parse
import urllib.request
from enum import Enum
from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.contrib.gis.geos import Point
from django.db import models, transaction
from django.http import JsonResponse
from django.shortcuts import render, redirect, get_object_or_404
from .models import Restaurant, RestaurantList, RestaurantListItem
from .forms import RestaurantForm, RestaurantListForm, RestaurantListItemForm, CustomUserCreationForm


class OSMType(Enum):
    NODE = 'N'
    WAY = 'W'
    RELATION = 'R'


def index(request):
    return render(request, 'lists/home.html')


def create_restaurant_from_osm(osm_type: OSMType, osm_id):
    # Lookup restaurant details from Nominatim
    osm_id_with_type = f"{osm_type.value}{osm_id}"
    lookup_url = f"https://nominatim.openstreetmap.org/lookup?osm_ids={osm_id_with_type}&format=jsonv2"
    
    with urllib.request.urlopen(lookup_url, timeout=10) as response:
        data = json.loads(response.read().decode())
    
    if not data:
        raise ValueError(f"Restaurant not found. OSM Type: {osm_type.name}, OSM ID: {osm_id}, URL: {lookup_url}")
    
    item = data[0]
    # Parse address components
    address_parts = item.get('display_name', '').split(', ')
    
    # Create Point from lat/lon if available
    location = None
    if item.get('lat') and item.get('lon'):
        try:
            lat = float(item['lat'])
            lon = float(item['lon'])
            location = Point(lon, lat)  # Point(longitude, latitude)
        except (ValueError, TypeError):
            pass  # Keep location as None if conversion fails
    
    restaurant = Restaurant.objects.create(
        name=address_parts[0] if address_parts else '',
        address=item.get('display_name', ''),
        suburb=item.get('address', {}).get('suburb', ''),
        region=item.get('address', {}).get('state', ''),
        country=item.get('address', {}).get('country', ''),
        osm_type=osm_type.value,
        osm_id=osm_id,
        location=location
    )
    return restaurant


def restaurant_nominatim(request):
    if request.method == 'GET':
        query = request.GET.get('q', '')
        if query:
            # Search Nominatim API
            encoded_query = urllib.parse.quote(f"restaurant {query}")
            url = f"https://nominatim.openstreetmap.org/search?q={encoded_query}&format=jsonv2&limit=20"
            
            try:
                with urllib.request.urlopen(url, timeout=10) as response:
                    data = json.loads(response.read().decode())
                
                # Filter results to only include restaurants/food establishments
                restaurants = [
                    {
                        'name': item.get('display_name', '').split(',')[0],
                        'display_name': item.get('display_name', ''),
                        'address': item.get('display_name', ''),
                        'lat': item.get('lat'),
                        'lon': item.get('lon'),
                        'osm_type': item.get('osm_type'),
                        'osm_id': item.get('osm_id'),
                    }
                    for item in data
                    if 'amenity' in item.get('category', '') or 'restaurant' in item.get('type', '').lower()
                ]
                
                return render(request, 'lists/restaurant_search.html', {'restaurants': restaurants, 'query': query})
            except Exception as e:
                return render(request, 'lists/restaurant_search.html', {'error': str(e), 'query': query})
        
        return render(request, 'lists/restaurant_search.html')
    
    elif request.method == 'POST':
        # Add restaurant to database
        form = RestaurantForm(request.POST)
        if form.is_valid():
            osm_type = form.cleaned_data['osm_type']
            osm_id = form.cleaned_data['osm_id']
            
            try:
                # Convert string to OSMType enum
                type_mapping = {'node': OSMType.NODE, 'way': OSMType.WAY, 'relation': OSMType.RELATION}
                osm_type_enum = type_mapping.get(osm_type)
                if not osm_type_enum:
                    raise ValueError(f"Invalid OSM type: {osm_type}")
                
                restaurant = create_restaurant_from_osm(osm_type_enum, osm_id)
                messages.success(request, f'Restaurant "{restaurant.name}" added to database!')
                return redirect('restaurant_detail', restaurant_id=restaurant.id)
            except Exception as e:
                messages.error(request, f'Error adding restaurant: {str(e)}')
                return render(request, 'lists/restaurant_search.html', {'error': str(e)})
        else:
            return render(request, 'lists/restaurant_search.html', {'form': form})


def restaurant_index(request):
    restaurants = Restaurant.objects.all()
    return render(request, 'lists/restaurant_index.html', {'restaurants': restaurants})


def restaurantlist_index(request):
    restaurant_lists = RestaurantList.objects.all()
    return render(request, 'lists/restaurant_list_index.html', {'restaurant_lists': restaurant_lists})


def restaurantlist_detail(request, list_id):
    restaurant_list = get_object_or_404(RestaurantList, id=list_id)
    list_items = RestaurantListItem.objects.filter(restaurant_list=restaurant_list).order_by('order')
    return render(request, 'lists/restaurant_list_detail.html', {
        'restaurant_list': restaurant_list,
        'list_items': list_items
    })


@login_required
def restaurantlist_create(request):
    if request.method == 'POST':
        form = RestaurantListForm(request.POST)
        if form.is_valid():
            restaurant_list = form.save(commit=False)
            restaurant_list.owner = request.user
            restaurant_list.save()
            messages.success(request, f'Restaurant list "{restaurant_list.name}" created successfully!')
            return redirect('restaurantlist_index')
    else:
        form = RestaurantListForm()
    
    return render(request, 'lists/restaurant_list_create.html', {'form': form})


@login_required
def restaurantlistitem_create(request, list_id):
    restaurant_list = get_object_or_404(RestaurantList, id=list_id)
    
    # Check if user owns the list
    if restaurant_list.owner != request.user:
        messages.error(request, "You don't have permission to add items to this list.")
        return redirect('restaurantlist_detail', list_id=list_id)
    
    if request.method == 'POST':
        form = RestaurantListItemForm(request.POST)
        if form.is_valid():
            list_item = form.save(commit=False)
            list_item.restaurant_list = restaurant_list
            # Auto-generate order to add to end of list
            max_order = RestaurantListItem.objects.filter(restaurant_list=restaurant_list).aggregate(
                max_order=models.Max('order')
            )['max_order']
            list_item.order = (max_order or 0) + 1
            list_item.save()
            messages.success(request, f'"{list_item.restaurant.name}" added to "{restaurant_list.name}"!')
            return redirect('restaurantlist_detail', list_id=restaurant_list.id)
    else:
        form = RestaurantListItemForm()
    
    return render(request, 'lists/restaurant_list_item_create.html', {
        'form': form, 
        'restaurant_list': restaurant_list
    })


def register(request):
    if request.method == 'POST':
        form = CustomUserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            return redirect('index')
    else:
        form = CustomUserCreationForm()
    
    return render(request, 'registration/register.html', {'form': form})


def restaurant_detail(request, restaurant_id):
    restaurant = get_object_or_404(Restaurant, id=restaurant_id)
    return render(request, 'lists/restaurant_detail.html', {'restaurant': restaurant})


@login_required
def move_item_up(request, item_id):
    item = get_object_or_404(RestaurantListItem, id=item_id)
    
    # Check if user owns the list
    if item.restaurant_list.owner != request.user:
        messages.error(request, "You don't have permission to modify this list.")
        return redirect('restaurantlist_detail', list_id=item.restaurant_list.id)
    
    with transaction.atomic():
        # Find the item with the next lower order (the one to swap with)
        previous_item = RestaurantListItem.objects.filter(
            restaurant_list=item.restaurant_list,
            order__lt=item.order
        ).order_by('-order').first()
        
        if previous_item:
            # Swap the order values
            item.order, previous_item.order = previous_item.order, item.order
            item.save()
            previous_item.save()
    
    return redirect('restaurantlist_detail', list_id=item.restaurant_list.id)


@login_required
def move_item_down(request, item_id):
    item = get_object_or_404(RestaurantListItem, id=item_id)
    
    # Check if user owns the list
    if item.restaurant_list.owner != request.user:
        messages.error(request, "You don't have permission to modify this list.")
        return redirect('restaurantlist_detail', list_id=item.restaurant_list.id)
    
    with transaction.atomic():
        # Find the item with the next higher order (the one to swap with)
        next_item = RestaurantListItem.objects.filter(
            restaurant_list=item.restaurant_list,
            order__gt=item.order
        ).order_by('order').first()
        
        if next_item:
            # Swap the order values
            item.order, next_item.order = next_item.order, item.order
            item.save()
            next_item.save()
    
    return redirect('restaurantlist_detail', list_id=item.restaurant_list.id)
