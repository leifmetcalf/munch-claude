import json
import urllib.parse
import urllib.request
from collections import defaultdict
from enum import Enum
from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.contrib.gis.geos import Point
from django.core.serializers.json import DjangoJSONEncoder
from django.db import models, transaction
from django.http import JsonResponse
from django.shortcuts import render, redirect, get_object_or_404
from .models import Restaurant, RestaurantList, RestaurantListItem, RestaurantImage, User
from .forms import RestaurantForm, RestaurantListForm, RestaurantListItemForm, CustomUserCreationForm, RestaurantImageForm


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
    
    # Create Point from lat/lon - required field
    if not item.get('lat') or not item.get('lon'):
        raise ValueError(f"Missing latitude or longitude data from Nominatim for OSM {osm_type.name}:{osm_id}")
    
    try:
        lat = float(item['lat'])
        lon = float(item['lon'])
        location = Point(lon, lat)  # Point(longitude, latitude)
    except (ValueError, TypeError) as e:
        raise ValueError(f"Invalid latitude/longitude data from Nominatim: lat={item.get('lat')}, lon={item.get('lon')}") from e
    
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
    """Import restaurants from Nominatim API into the database.
    
    This view's purpose is to search for restaurants via Nominatim and add them
    to the local database. It does NOT add restaurants to user lists - that's
    handled by other views after the restaurant exists in the database.
    """
    if request.method == 'GET':
        query = request.GET.get('q', '')
        if query:
            # Search Nominatim API
            encoded_query = urllib.parse.quote(query)
            url = f"https://nominatim.openstreetmap.org/search?q={encoded_query}&format=jsonv2"
            
            # Print the Nominatim search request
            print(f"Nominatim search request: {url}")
            
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
    query = request.GET.get('q', '').strip()
    
    if query:
        # Search restaurants by name, address, suburb, region, or country
        restaurants = Restaurant.objects.filter(
            models.Q(name__icontains=query) |
            models.Q(address__icontains=query) |
            models.Q(suburb__icontains=query) |
            models.Q(region__icontains=query) |
            models.Q(country__icontains=query)
        ).order_by('name')
    else:
        restaurants = Restaurant.objects.all().order_by('name')
    
    return render(request, 'lists/restaurant_index.html', {
        'restaurants': restaurants,
        'query': query
    })


def restaurantlist_index(request):
    query = request.GET.get('q', '')
    restaurant_lists = RestaurantList.objects.all()
    
    if query:
        # Search by list name or owner username
        restaurant_lists = restaurant_lists.filter(
            models.Q(name__icontains=query) |
            models.Q(owner__username__icontains=query)
        )
    
    return render(request, 'lists/restaurant_list_index.html', {
        'restaurant_lists': restaurant_lists,
        'query': query
    })


def restaurantlist_detail(request, list_id):
    restaurant_list = get_object_or_404(RestaurantList, id=list_id)
    list_items = RestaurantListItem.objects.filter(restaurant_list=restaurant_list).order_by('order')
    
    # Extract coordinates for the map
    restaurant_coordinates = []
    for item in list_items:
        if item.restaurant.location:
            restaurant_coordinates.append({
                'lat': item.restaurant.location.y,  # latitude
                'lng': item.restaurant.location.x,  # longitude
                'name': item.restaurant.name,
                'address': item.restaurant.address,
                'notes': item.notes or ''
            })
    
    return render(request, 'lists/restaurant_list_detail.html', {
        'restaurant_list': restaurant_list,
        'list_items': list_items,
        'restaurant_coordinates': restaurant_coordinates,
        'restaurant_coordinates_json': json.dumps(restaurant_coordinates, cls=DjangoJSONEncoder)
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
def restaurantlistitem_create(request):
    """Unified view for adding restaurants to lists.
    
    Query parameters can be used to preset form values:
    - ?list=<id>: Pre-select a list
    - ?restaurant=<id>: Pre-select a restaurant
    """
    # Check if user has lists
    user_lists = RestaurantList.objects.filter(owner=request.user)
    if not user_lists.exists():
        messages.error(request, "You don't have any restaurant lists. Create one first.")
        return redirect('restaurantlist_create')
    
    # Get preset values from query params
    preset_list_id = request.GET.get('list')
    preset_restaurant_id = request.GET.get('restaurant')
    
    if request.method == 'POST':
        form = RestaurantListItemForm(request.POST)
        
        if form.is_valid():
            # Verify user owns the selected list
            if form.cleaned_data['restaurant_list'].owner != request.user:
                messages.error(request, "You don't have permission to add items to this list.")
                return redirect('restaurantlist_index')
            
            list_item = form.save(commit=False)
            
            # Auto-generate order to add to end of list
            max_order = RestaurantListItem.objects.filter(
                restaurant_list=list_item.restaurant_list
            ).aggregate(models.Max('order'))['order__max'] or 0
            list_item.order = max_order + 1
            
            list_item.save()
            messages.success(request, f'"{list_item.restaurant.name}" added to "{list_item.restaurant_list.name}"!')
            
            # Redirect based on where user came from
            if preset_restaurant_id:
                return redirect('restaurant_detail', restaurant_id=list_item.restaurant.id)
            elif preset_list_id:
                return redirect('restaurantlist_detail', list_id=list_item.restaurant_list.id)
            else:
                return redirect('restaurantlistitem_create')
    else:
        # Initialize form with preset values from query params
        initial = {}
        if preset_restaurant_id:
            try:
                restaurant_obj = Restaurant.objects.get(pk=preset_restaurant_id)
                initial['restaurant'] = restaurant_obj
            except Restaurant.DoesNotExist:
                pass
        
        if preset_list_id:
            try:
                list_obj = RestaurantList.objects.get(pk=preset_list_id, owner=request.user)
                initial['restaurant_list'] = list_obj
            except RestaurantList.DoesNotExist:
                pass
        
        form = RestaurantListItemForm(initial=initial)
    
    # Get preset objects for template
    preset_list = None
    preset_restaurant = None
    
    if preset_list_id:
        try:
            preset_list = RestaurantList.objects.get(pk=preset_list_id, owner=request.user)
        except RestaurantList.DoesNotExist:
            pass
    
    if preset_restaurant_id:
        try:
            preset_restaurant = Restaurant.objects.get(pk=preset_restaurant_id)
        except Restaurant.DoesNotExist:
            pass
    
    return render(request, 'lists/restaurant_list_item_create.html', {
        'form': form,
        'user_lists': user_lists,
        'preset_list': preset_list,
        'preset_restaurant': preset_restaurant
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
    
    # Extract coordinates for the map
    coordinates = None
    if restaurant.location:
        coordinates = {
            'lat': restaurant.location.y,  # latitude
            'lng': restaurant.location.x   # longitude
        }
    
    # Get all list items for this restaurant with deduplication logic
    all_list_items = RestaurantListItem.objects.filter(
        restaurant=restaurant
    ).select_related('restaurant_list__owner').order_by('-inserted_at')
    
    # Group items by list, separating those with and without comments
    items_by_list = defaultdict(lambda: {'with_comments': [], 'without_comments': []})
    
    for item in all_list_items:
        list_id = item.restaurant_list.id
        key = 'with_comments' if item.notes else 'without_comments'
        items_by_list[list_id][key].append(item)
    
    # Build final list: all items with comments + one fallback per list without any comments
    list_items = [
        item
        for list_data in items_by_list.values()
        for item in (
            list_data['with_comments'] or 
            list_data['without_comments'][:1]  # Take only the first (most recent) if no comments
        )
    ]
    
    # Sort by insertion time (newest first)
    list_items.sort(key=lambda item: item.inserted_at, reverse=True)
    
    return render(request, 'lists/restaurant_detail.html', {
        'restaurant': restaurant,
        'coordinates': coordinates,
        'list_items': list_items
    })


@login_required
def restaurant_image_add(request, restaurant_id):
    restaurant = get_object_or_404(Restaurant, id=restaurant_id)
    
    if request.method == 'POST':
        form = RestaurantImageForm(request.POST, request.FILES)
        if form.is_valid():
            image = form.save(commit=False)
            image.restaurant = restaurant
            image.added_by = request.user
            image.save()
            messages.success(request, f'Image added for "{restaurant.name}"!')
            return redirect('restaurant_detail', restaurant_id=restaurant.id)
    else:
        form = RestaurantImageForm()
    
    return render(request, 'lists/restaurant_image_add.html', {
        'form': form,
        'restaurant': restaurant
    })


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
    
    return redirect('restaurantlist_edit', list_id=item.restaurant_list.id)


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
    
    return redirect('restaurantlist_edit', list_id=item.restaurant_list.id)


@login_required
def restaurantlist_edit(request, list_id):
    restaurant_list = get_object_or_404(RestaurantList, id=list_id)
    
    # Check if user owns the list
    if restaurant_list.owner != request.user:
        messages.error(request, "You don't have permission to edit this list.")
        return redirect('restaurantlist_detail', list_id=list_id)
    
    list_items = RestaurantListItem.objects.filter(restaurant_list=restaurant_list).order_by('order')
    return render(request, 'lists/restaurant_list_edit.html', {
        'restaurant_list': restaurant_list,
        'list_items': list_items
    })


@login_required
def restaurantlist_update(request, list_id):
    restaurant_list = get_object_or_404(RestaurantList, id=list_id)
    
    # Check if user owns the list
    if restaurant_list.owner != request.user:
        messages.error(request, "You don't have permission to edit this list.")
        return redirect('restaurantlist_detail', list_id=list_id)
    
    if request.method == 'POST':
        form = RestaurantListForm(request.POST, instance=restaurant_list)
        if form.is_valid():
            form.save()
            messages.success(request, "List details updated successfully!")
        else:
            messages.error(request, "Please correct the errors below.")
    
    return redirect('restaurantlist_edit', list_id=list_id)


@login_required
def restaurantlistitem_delete(request, item_id):
    item = get_object_or_404(RestaurantListItem, id=item_id)
    
    # Check if user owns the list
    if item.restaurant_list.owner != request.user:
        messages.error(request, "You don't have permission to delete items from this list.")
        return redirect('restaurantlist_detail', list_id=item.restaurant_list.id)
    
    restaurant_name = item.restaurant.name
    list_id = item.restaurant_list.id
    item.delete()
    
    messages.success(request, f'"{restaurant_name}" removed from the list.')
    return redirect('restaurantlist_edit', list_id=list_id)


def restaurant_search_api(request):
    """API endpoint for restaurant autocomplete search.
    
    Returns JSON with restaurant matches for the given query.
    """
    query = request.GET.get('q', '').strip()
    
    if not query or len(query) < 2:
        return JsonResponse({'restaurants': []})
    
    # Search restaurants by name, address, or suburb
    restaurants = Restaurant.objects.filter(
        models.Q(name__icontains=query) |
        models.Q(address__icontains=query) |
        models.Q(suburb__icontains=query)
    ).order_by('name')[:20]
    
    # Format results for JSON response
    results = []
    for restaurant in restaurants:
        results.append({
            'id': restaurant.id,
            'name': restaurant.name,
            'address': restaurant.address,
            'suburb': restaurant.suburb or '',
            'display_text': f"{restaurant.name} - {restaurant.address}"
        })
    
    return JsonResponse({'restaurants': results})


def profile(request, user_id):
    profile_user = get_object_or_404(User, id=user_id)
    
    # Get user's restaurant lists
    user_lists = RestaurantList.objects.filter(owner=profile_user).order_by('-inserted_at')
    
    # Get statistics
    total_lists = user_lists.count()
    total_restaurants = RestaurantListItem.objects.filter(
        restaurant_list__owner=profile_user
    ).values('restaurant_id').distinct().count()
    
    return render(request, 'lists/profile.html', {
        'profile_user': profile_user,
        'user_lists': user_lists,
        'total_lists': total_lists,
        'total_restaurants': total_restaurants
    })
