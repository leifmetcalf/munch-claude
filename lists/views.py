import json
import logging
import urllib.parse
import urllib.request

from requests_oauthlib import OAuth2Session

logger = logging.getLogger(__name__)
from collections import defaultdict
from django.conf import settings
from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from django.contrib.gis.geos import Point
from django.core.exceptions import PermissionDenied
from django.core.serializers.json import DjangoJSONEncoder
from django.db import models, transaction
from django.db.models import Prefetch
from django.http import JsonResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.utils import timezone
from .models import (
    Restaurant,
    RestaurantImage,
    RestaurantList,
    RestaurantListItem,
    User,
    ListFollow,
    MunchLog,
    MunchLogItem,
    OsmAccount,
)
from .forms import (
    RestaurantForm,
    RestaurantListForm,
    RestaurantListItemForm,
    CustomUserCreationForm,
    RestaurantImageForm,
    ListCommentForm,
    MunchLogItemForm,
    MunchLogItemUpdateForm,
    EditProfileForm,
    RestaurantCreateForm,
)
from .gemini_integration import get_restaurant_details_from_gemini
from .osm_integration import (
    build_restaurant_tags,
    build_node_xml,
    create_restaurant_node,
    OsmAuthError,
)


def index(request):
    # Get recent activity - both restaurant list items and munch log items
    # We'll combine them and sort by insertion time
    from itertools import chain
    from operator import attrgetter

    # Get the 12 most recently added restaurant list items
    recent_list_items = RestaurantListItem.objects.select_related(
        "restaurant", "restaurant_list", "restaurant_list__owner"
    ).order_by("-created_at")[:12]

    # Get the 12 most recently added munch log items
    recent_munch_items = MunchLogItem.objects.select_related(
        "restaurant", "munch_log", "munch_log__owner"
    ).order_by("-created_at")[:12]

    # Combine and sort by insertion time, then take the top 6
    all_recent_items = sorted(
        chain(recent_list_items, recent_munch_items),
        key=attrgetter("created_at"),
        reverse=True,
    )[:6]

    # Separate them by type for the template
    recent_items = []
    for item in all_recent_items:
        if isinstance(item, RestaurantListItem):
            recent_items.append(
                {"type": "list_item", "item": item, "created_at": item.created_at}
            )
        else:  # MunchLogItem
            recent_items.append(
                {"type": "munch_item", "item": item, "created_at": item.created_at}
            )

    # If user is authenticated, also get activity from lists they're following
    following_activity = []
    if request.user.is_authenticated:
        followed_lists = ListFollow.objects.filter(follower=request.user).values_list(
            "restaurant_list_id", flat=True
        )
        following_list_items = (
            RestaurantListItem.objects.filter(restaurant_list_id__in=followed_lists)
            .select_related("restaurant", "restaurant_list", "restaurant_list__owner")
            .order_by("-created_at")[:6]
        )

        # For following activity, we only show list items since we don't have user following
        for item in following_list_items:
            following_activity.append(
                {"type": "list_item", "item": item, "created_at": item.created_at}
            )

    # Get all restaurants that have been munched by anyone
    munched_restaurant_ids = MunchLogItem.objects.values_list(
        "restaurant_id", flat=True
    ).distinct()
    munched_restaurants = Restaurant.objects.filter(id__in=munched_restaurant_ids)

    # Build coordinates for the map
    munched_coordinates = [
        {
            "id": restaurant.id,
            "lat": restaurant.location.y,
            "lng": restaurant.location.x,
            "name": restaurant.name,
        }
        for restaurant in munched_restaurants
    ]

    return render(
        request,
        "lists/home.html",
        {
            "recent_items": recent_items,
            "following_activity": following_activity,
            "munched_coordinates": munched_coordinates,
            "munched_coordinates_json": json.dumps(
                munched_coordinates, cls=DjangoJSONEncoder
            ),
        },
    )


def fetch_restaurant_data_from_nominatim(osm_type: Restaurant.OSMType, osm_id):
    """Fetch restaurant data from Nominatim Lookup API.

    Returns a dict with restaurant field values.
    """
    # Lookup restaurant details from Nominatim
    osm_id_with_type = f"{osm_type}{osm_id}"
    lookup_url = f"https://nominatim.openstreetmap.org/lookup?osm_ids={osm_id_with_type}&format=jsonv2"

    with urllib.request.urlopen(lookup_url, timeout=10) as response:
        data = json.loads(response.read().decode())

    if not data:
        raise ValueError(
            f"Restaurant not found. OSM Type: {osm_type}, OSM ID: {osm_id}, URL: {lookup_url}"
        )

    item = data[0]
    # Parse address components
    address_parts = item.get("display_name", "").split(", ")

    # Create Point from lat/lon - required field
    if not item.get("lat") or not item.get("lon"):
        raise ValueError(
            f"Missing latitude or longitude data from Nominatim for OSM {osm_type}:{osm_id}"
        )

    try:
        lat = float(item["lat"])
        lon = float(item["lon"])
        location = Point(lon, lat)  # Point(longitude, latitude)
    except (ValueError, TypeError) as e:
        raise ValueError(
            f"Invalid latitude/longitude data from Nominatim: lat={item.get('lat')}, lon={item.get('lon')}"
        ) from e

    return {
        "name": address_parts[0] if address_parts else "",
        "address": item.get("display_name", ""),
        "suburb": item.get("address", {}).get("suburb", ""),
        "region": item.get("address", {}).get("state", ""),
        "country": item.get("address", {}).get("country", ""),
        "location": location,
    }


def create_restaurant_from_osm(osm_type: Restaurant.OSMType, osm_id, added_by):
    """Create a new restaurant from OSM data.

    Args:
        osm_type: The OSM type (NODE, WAY, or RELATION)
        osm_id: The OSM ID
        added_by: The user who is importing this restaurant (required)
    """
    data = fetch_restaurant_data_from_nominatim(osm_type, osm_id)

    restaurant = Restaurant.objects.create(
        osm_type=osm_type, osm_id=osm_id, added_by=added_by, **data
    )
    return restaurant


@login_required
def restaurant_nominatim(request):
    """Import restaurants from Nominatim API into the database.

    This view's purpose is to search for restaurants via Nominatim and add them
    to the local database. It does NOT add restaurants to user lists - that's
    handled by other views after the restaurant exists in the database.
    """
    if request.method == "GET":
        query = request.GET.get("q", "")
        if query:
            # Search Nominatim API
            encoded_query = urllib.parse.quote(query)
            url = f"https://nominatim.openstreetmap.org/search?q={encoded_query}&format=jsonv2"

            logger.debug("Nominatim search request: %s", url)

            try:
                with urllib.request.urlopen(url, timeout=10) as response:
                    data = json.loads(response.read().decode())

                # Filter results to only include restaurants/food establishments
                restaurants = [
                    {
                        "name": item.get("display_name", "").split(",")[0],
                        "display_name": item.get("display_name", ""),
                        "address": item.get("display_name", ""),
                        "lat": item.get("lat"),
                        "lon": item.get("lon"),
                        "osm_type": item.get("osm_type"),
                        "osm_id": item.get("osm_id"),
                    }
                    for item in data
                ]

                return render(
                    request,
                    "lists/restaurant_search.html",
                    {"restaurants": restaurants, "query": query},
                )
            except Exception as e:
                return render(
                    request,
                    "lists/restaurant_search.html",
                    {"error": str(e), "query": query},
                )

        return render(request, "lists/restaurant_search.html")

    elif request.method == "POST":
        # Add restaurant to database
        form = RestaurantForm(request.POST)
        if form.is_valid():
            osm_type = form.cleaned_data["osm_type"]
            osm_id = form.cleaned_data["osm_id"]

            try:
                # Convert string to OSMType value
                type_mapping = {
                    "node": Restaurant.OSMType.NODE,
                    "way": Restaurant.OSMType.WAY,
                    "relation": Restaurant.OSMType.RELATION,
                }
                osm_type_value = type_mapping.get(osm_type)
                if not osm_type_value:
                    raise ValueError(f"Invalid OSM type: {osm_type}")

                # Check if restaurant already exists
                try:
                    existing_restaurant = Restaurant.objects.get(
                        osm_type=osm_type_value, osm_id=osm_id
                    )
                except Restaurant.DoesNotExist:
                    existing_restaurant = None

                if existing_restaurant:
                    messages.info(
                        request,
                        f'"{existing_restaurant.name}" already exists in MunchZone. Redirecting to "{existing_restaurant.name}".',
                    )
                    return redirect(
                        "restaurant_detail", restaurant_id=existing_restaurant.id
                    )

                restaurant = create_restaurant_from_osm(
                    osm_type_value, osm_id, added_by=request.user
                )
                messages.success(
                    request, f'Restaurant "{restaurant.name}" added to database!'
                )
                return redirect("restaurant_detail", restaurant_id=restaurant.id)
            except Exception as e:
                messages.error(request, f"Error adding restaurant: {str(e)}")
                return render(
                    request, "lists/restaurant_search.html", {"error": str(e)}
                )
        else:
            return render(request, "lists/restaurant_search.html", {"form": form})


def restaurant_index(request):
    query = request.GET.get("q", "").strip()

    if query:
        # Search restaurants by name, address, suburb, region, or country
        restaurants = Restaurant.objects.filter(
            models.Q(name__icontains=query)
            | models.Q(address__icontains=query)
            | models.Q(suburb__icontains=query)
            | models.Q(region__icontains=query)
            | models.Q(country__icontains=query)
        ).order_by("name")
    else:
        restaurants = Restaurant.objects.all().order_by("name")

    return render(
        request,
        "lists/restaurant_index.html",
        {"restaurants": restaurants, "query": query},
    )


def restaurantlist_index(request):
    query = request.GET.get("q", "")
    restaurant_lists = RestaurantList.objects.annotate(
        follower_count=models.Count("followers")
    )

    if query:
        # Search by list name or owner username
        restaurant_lists = restaurant_lists.filter(
            models.Q(name__icontains=query) | models.Q(owner__username__icontains=query)
        )

    return render(
        request,
        "lists/restaurant_list_index.html",
        {"restaurant_lists": restaurant_lists, "query": query},
    )


def user_restaurantlist_index(request, user_id):
    list_user = get_object_or_404(User, id=user_id)
    query = request.GET.get("q", "")
    restaurant_lists = RestaurantList.objects.filter(owner=list_user).annotate(
        follower_count=models.Count("followers")
    )

    if query:
        # Search by list name
        restaurant_lists = restaurant_lists.filter(name__icontains=query)

    return render(
        request,
        "lists/user_restaurant_list_index.html",
        {"restaurant_lists": restaurant_lists, "query": query, "list_user": list_user},
    )


def restaurantlist_detail(request, list_id, comment_form=None):
    restaurant_list = get_object_or_404(RestaurantList, id=list_id)
    list_items = (
        RestaurantListItem.objects.filter(restaurant_list=restaurant_list)
        .select_related("restaurant")
        .prefetch_related(
            Prefetch(
                "restaurant__images",
                queryset=RestaurantImage.objects.order_by("id")[:1],
                to_attr="first_image_list",
            )
        )
        .order_by("order")
    )
    comments = restaurant_list.comments.all()

    # Check if current user is following this list
    is_following = False
    if request.user.is_authenticated:
        is_following = ListFollow.objects.filter(
            follower=request.user, restaurant_list=restaurant_list
        ).exists()

    # Get follower count
    follower_count = restaurant_list.followers.count()

    if comment_form is None and request.user.is_authenticated:
        comment_form = ListCommentForm(
            initial={"restaurant_list": restaurant_list, "author": request.user}
        )

    # Extract coordinates for the map
    restaurant_coordinates = []
    for item in list_items:
        if item.restaurant.location:
            restaurant_coordinates.append(
                {
                    "lat": item.restaurant.location.y,  # latitude
                    "lng": item.restaurant.location.x,  # longitude
                    "name": item.restaurant.name,
                    "address": item.restaurant.address,
                    "notes": item.notes or "",
                }
            )

    return render(
        request,
        "lists/restaurant_list_detail.html",
        {
            "restaurant_list": restaurant_list,
            "list_items": list_items,
            "comments": comments,
            "comment_form": comment_form,
            "restaurant_coordinates": restaurant_coordinates,
            "restaurant_coordinates_json": json.dumps(
                restaurant_coordinates, cls=DjangoJSONEncoder
            ),
            "is_following": is_following,
            "follower_count": follower_count,
        },
    )


@login_required
@require_POST
def list_comment_create(request, list_id):
    comment_form = ListCommentForm(request.POST)
    if comment_form.is_valid():
        if comment_form.cleaned_data["author"] != request.user:
            messages.error(request, "You can only post comments as yourself.")
        else:
            comment_form.save()
            messages.success(request, "Your comment has been added!")
        return redirect("restaurantlist_detail", list_id=list_id)
    return restaurantlist_detail(request, list_id, comment_form=comment_form)


@login_required
def restaurantlist_create(request):
    if request.method == "POST":
        form = RestaurantListForm(request.POST)
        if form.is_valid():
            restaurant_list = form.save()
            messages.success(
                request,
                f'Restaurant list "{restaurant_list.name}" created successfully!',
            )
            return redirect("restaurantlist_index")
    else:
        form = RestaurantListForm(initial={"owner": request.user})

    return render(request, "lists/restaurant_list_create.html", {"form": form})


@login_required
def restaurantlistitem_create(request):
    """View for adding restaurants to lists.

    Query parameters can be used to set default form values:
    - ?list=<id>: Pre-select a list
    - ?restaurant=<id>: Pre-select a restaurant
    """
    # Get all user's lists
    user_lists = RestaurantList.objects.filter(owner=request.user).order_by(
        "-created_at"
    )

    # Get URL parameter values
    list_id = request.GET.get("list")
    restaurant_id = request.GET.get("restaurant")

    if request.method == "POST":
        form = RestaurantListItemForm(request.POST)
        if form.is_valid():
            # Verify user owns the selected list
            if form.cleaned_data["restaurant_list"].owner != request.user:
                raise PermissionDenied

            list_item = form.save(commit=False)

            # Auto-generate order to add to end of list
            max_order = (
                RestaurantListItem.objects.filter(
                    restaurant_list=list_item.restaurant_list
                ).aggregate(models.Max("order"))["order__max"]
                or 0
            )
            list_item.order = max_order + 1

            list_item.save()
            messages.success(
                request,
                f'"{list_item.restaurant.name}" added to "{list_item.restaurant_list.name}"!',
            )

            # Redirect based on where user came from
            if restaurant_id:
                return redirect(
                    "restaurant_detail", restaurant_id=list_item.restaurant.id
                )
            elif list_id:
                return redirect(
                    "restaurantlist_detail", list_id=list_item.restaurant_list.id
                )
            else:
                return redirect("restaurantlistitem_create")
    else:
        # Initialize form with URL parameter values
        initial = {}

        if restaurant_id:
            try:
                restaurant = Restaurant.objects.get(pk=restaurant_id)
                initial["restaurant"] = restaurant
            except Restaurant.DoesNotExist:
                pass

        if list_id:
            try:
                list_obj = RestaurantList.objects.get(pk=list_id, owner=request.user)
                initial["restaurant_list"] = list_obj
            except RestaurantList.DoesNotExist:
                pass

        form = RestaurantListItemForm(initial=initial)

    # Get selected restaurant info for display
    selected_restaurant = None
    if restaurant_id:
        try:
            selected_restaurant = Restaurant.objects.get(pk=restaurant_id)
        except Restaurant.DoesNotExist:
            pass

    return render(
        request,
        "lists/restaurant_list_item_create.html",
        {
            "form": form,
            "user_lists": user_lists,
            "selected_list_id": list_id,
            "selected_restaurant_id": restaurant_id,
            "selected_restaurant": selected_restaurant,
        },
    )


def register(request):
    if request.method == "POST":
        form = CustomUserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            return redirect("index")
    else:
        form = CustomUserCreationForm()

    return render(request, "registration/register.html", {"form": form})


def restaurant_detail(request, restaurant_id):
    restaurant = get_object_or_404(Restaurant, id=restaurant_id)

    # Extract coordinates for the map
    coordinates = None
    if restaurant.location:
        coordinates = {
            "lat": restaurant.location.y,  # latitude
            "lng": restaurant.location.x,  # longitude
        }

    # Get all list items for this restaurant with deduplication logic
    all_list_items = (
        RestaurantListItem.objects.filter(restaurant=restaurant)
        .select_related("restaurant_list__owner")
        .order_by("-created_at")
    )

    # Group items by list, separating those with and without comments
    items_by_list = defaultdict(lambda: {"with_comments": [], "without_comments": []})

    for item in all_list_items:
        list_id = item.restaurant_list.id
        key = "with_comments" if item.notes else "without_comments"
        items_by_list[list_id][key].append(item)

    # Build final list: all items with comments + one fallback per list without any comments
    list_items = [
        item
        for list_data in items_by_list.values()
        for item in (
            list_data["with_comments"]
            or list_data["without_comments"][
                :1
            ]  # Take only the first (most recent) if no comments
        )
    ]

    # Sort by insertion time (newest first)
    list_items.sort(key=lambda item: item.created_at, reverse=True)

    # Get users who have munched at this restaurant (from munch logs only)
    munchers = (
        MunchLogItem.objects.filter(restaurant=restaurant)
        .select_related("munch_log__owner")
        .values("munch_log__owner__id", "munch_log__owner__username")
        .distinct()
        .order_by("munch_log__owner__username")
    )

    return render(
        request,
        "lists/restaurant_detail.html",
        {
            "restaurant": restaurant,
            "coordinates": coordinates,
            "list_items": list_items,
            "munchers": munchers,
        },
    )


@login_required
def restaurant_image_add(request, restaurant_id):
    restaurant = get_object_or_404(Restaurant, id=restaurant_id)

    if request.method == "POST":
        form = RestaurantImageForm(request.POST, request.FILES)
        if form.is_valid():
            form.save()
            messages.success(request, f'Image added for "{restaurant.name}"!')
            return redirect("restaurant_detail", restaurant_id=restaurant.id)
    else:
        form = RestaurantImageForm(
            initial={"restaurant": restaurant, "added_by": request.user}
        )

    return render(
        request,
        "lists/restaurant_image_add.html",
        {"form": form, "restaurant": restaurant},
    )


@login_required
def restaurant_image_delete(request, image_id):
    image = get_object_or_404(RestaurantImage, id=image_id)

    if image.added_by != request.user:
        raise PermissionDenied

    restaurant = image.restaurant

    if request.method == "POST":
        image.delete()
        messages.success(request, "Image deleted!")
        return redirect("restaurant_detail", restaurant_id=restaurant.id)

    return redirect("restaurant_detail", restaurant_id=restaurant.id)


@login_required
def move_item_up(request, item_id):
    item = get_object_or_404(RestaurantListItem, id=item_id)

    # Check if user owns the list
    if item.restaurant_list.owner != request.user:
        raise PermissionDenied

    with transaction.atomic():
        # Find the item with the next lower order (the one to swap with)
        previous_item = (
            RestaurantListItem.objects.filter(
                restaurant_list=item.restaurant_list, order__lt=item.order
            )
            .order_by("-order")
            .first()
        )

        if previous_item:
            # Swap the order values
            item.order, previous_item.order = previous_item.order, item.order
            item.save()
            previous_item.save()

    return redirect("restaurantlist_edit", list_id=item.restaurant_list.id)


@login_required
def move_item_down(request, item_id):
    item = get_object_or_404(RestaurantListItem, id=item_id)

    # Check if user owns the list
    if item.restaurant_list.owner != request.user:
        raise PermissionDenied

    with transaction.atomic():
        # Find the item with the next higher order (the one to swap with)
        next_item = (
            RestaurantListItem.objects.filter(
                restaurant_list=item.restaurant_list, order__gt=item.order
            )
            .order_by("order")
            .first()
        )

        if next_item:
            # Swap the order values
            item.order, next_item.order = next_item.order, item.order
            item.save()
            next_item.save()

    return redirect("restaurantlist_edit", list_id=item.restaurant_list.id)


@login_required
def restaurantlist_edit(request, list_id):
    restaurant_list = get_object_or_404(RestaurantList, id=list_id)

    # Check if user owns the list
    if restaurant_list.owner != request.user:
        raise PermissionDenied

    list_items = RestaurantListItem.objects.filter(
        restaurant_list=restaurant_list
    ).order_by("order")
    return render(
        request,
        "lists/restaurant_list_edit.html",
        {"restaurant_list": restaurant_list, "list_items": list_items},
    )


@login_required
def restaurantlist_update(request, list_id):
    restaurant_list = get_object_or_404(RestaurantList, id=list_id)

    # Check if user owns the list
    if restaurant_list.owner != request.user:
        raise PermissionDenied

    if request.method == "POST":
        form = RestaurantListForm(request.POST, instance=restaurant_list)
        if form.is_valid():
            form.save()
            messages.success(request, "List details updated successfully!")
        else:
            messages.error(request, "Please correct the errors below.")

    return redirect("restaurantlist_edit", list_id=list_id)


@login_required
def restaurantlist_delete(request, list_id):
    restaurant_list = get_object_or_404(RestaurantList, id=list_id)

    # Check if user owns the list
    if restaurant_list.owner != request.user:
        raise PermissionDenied

    if request.method == "POST":
        list_name = restaurant_list.name
        restaurant_list.delete()
        messages.success(request, f'List "{list_name}" has been deleted.')
        return redirect("user_restaurantlist_index", user_id=request.user.id)

    # For GET requests, redirect back to edit page
    return redirect("restaurantlist_edit", list_id=list_id)


@login_required
def restaurantlistitem_delete(request, item_id):
    item = get_object_or_404(RestaurantListItem, id=item_id)

    # Check if user owns the list
    if item.restaurant_list.owner != request.user:
        raise PermissionDenied

    restaurant_name = item.restaurant.name
    list_id = item.restaurant_list.id
    item.delete()

    messages.success(request, f'"{restaurant_name}" removed from the list.')
    return redirect("restaurantlist_edit", list_id=list_id)


def restaurant_search_api(request):
    """API endpoint for restaurant autocomplete search.

    Returns JSON with restaurant matches for the given query.
    """
    query = request.GET.get("q", "").strip()

    if not query or len(query) < 2:
        return JsonResponse({"restaurants": []})

    # Search restaurants by name, address, or suburb
    restaurants = Restaurant.objects.filter(
        models.Q(name__icontains=query)
        | models.Q(address__icontains=query)
        | models.Q(suburb__icontains=query)
    ).order_by("name")[:20]

    # Format results for JSON response
    results = []
    for restaurant in restaurants:
        results.append(
            {
                "id": restaurant.id,
                "name": restaurant.name,
                "address": restaurant.address,
                "suburb": restaurant.suburb or "",
                "display_text": f"{restaurant.name} - {restaurant.address}",
            }
        )

    return JsonResponse({"restaurants": results})


def profile(request, user_id):
    profile_user = get_object_or_404(User, id=user_id)

    # Get user's restaurant lists (munch log is now separate)
    user_lists = RestaurantList.objects.filter(owner=profile_user).order_by(
        "-created_at"
    )

    # Get statistics

    # Count munch log entries
    total_munches = 0
    try:
        total_munches = profile_user.munch_log.munchlogitem_set.count()
    except MunchLog.DoesNotExist:
        pass

    return render(
        request,
        "lists/profile.html",
        {
            "profile_user": profile_user,
            "user_lists": user_lists,
            "total_munches": total_munches,
        },
    )


@login_required
def toggle_list_follow(request, list_id):
    """Toggle following status for a restaurant list."""
    if request.method != "POST":
        return redirect("restaurantlist_detail", list_id=list_id)

    restaurant_list = get_object_or_404(RestaurantList, id=list_id)

    # Prevent users from following their own lists
    if restaurant_list.owner == request.user:
        messages.error(request, "You cannot follow your own list.")
        return redirect("restaurantlist_detail", list_id=list_id)

    follow, created = ListFollow.objects.get_or_create(
        follower=request.user, restaurant_list=restaurant_list
    )

    if created:
        messages.success(request, f'You are now following "{restaurant_list.name}"!')
    else:
        follow.delete()
        messages.success(request, f'You have unfollowed "{restaurant_list.name}".')

    return redirect("restaurantlist_detail", list_id=list_id)


def user_following_lists(request, user_id):
    """Show lists that a user is following."""
    followed_user = get_object_or_404(User, id=user_id)

    # Get all lists this user is following
    following = (
        ListFollow.objects.filter(follower=followed_user)
        .select_related("restaurant_list", "restaurant_list__owner")
        .order_by("-followed_at")
    )

    return render(
        request,
        "lists/user_following_lists.html",
        {"followed_user": followed_user, "following": following},
    )


def list_followers(request, list_id):
    """Show who follows a specific list."""
    restaurant_list = get_object_or_404(RestaurantList, id=list_id)

    # Get all followers of this list
    followers = (
        ListFollow.objects.filter(restaurant_list=restaurant_list)
        .select_related("follower")
        .order_by("-followed_at")
    )

    return render(
        request,
        "lists/list_followers.html",
        {"restaurant_list": restaurant_list, "followers": followers},
    )


def munch_log(request, user_id):
    """Display a user's Munch Log."""
    munch_log_user = get_object_or_404(User, id=user_id)

    # Get or create the user's munch log
    munch_log = munch_log_user.get_or_create_munch_log()

    # Get all items in the munch log
    munch_log_items = MunchLogItem.objects.filter(munch_log=munch_log).select_related(
        "restaurant", "image"
    )

    # Calculate unique munches (unique restaurants)
    unique_restaurants = munch_log_items.values("restaurant").distinct().count()

    # Calculate countries munched in
    countries = (
        munch_log_items.values("restaurant__country")
        .exclude(restaurant__country="")
        .distinct()
        .count()
    )

    # Extract coordinates for the map
    restaurant_coordinates = []
    for item in munch_log_items:
        if item.restaurant.location:
            restaurant_coordinates.append(
                {
                    "lat": item.restaurant.location.y,  # latitude
                    "lng": item.restaurant.location.x,  # longitude
                    "name": item.restaurant.name,
                    "address": item.restaurant.address,
                    "notes": item.notes or "",
                }
            )

    return render(
        request,
        "lists/munch_log_detail.html",
        {
            "munch_log": munch_log,
            "munch_log_items": munch_log_items,
            "total_munches": munch_log_items.count(),
            "unique_munches": unique_restaurants,
            "countries_munched": countries,
            "restaurant_coordinates": restaurant_coordinates,
            "restaurant_coordinates_json": json.dumps(
                restaurant_coordinates, cls=DjangoJSONEncoder
            ),
        },
    )


@login_required
def munchlogitem_create(request):
    """Dedicated view for adding restaurants to munch logs.

    Query parameters can be used to set default form values:
    - ?restaurant=<id>: Pre-select a restaurant
    """
    # Ensure user has a munch log
    munch_log = request.user.get_or_create_munch_log()

    # Get URL parameter values
    restaurant_id = request.GET.get("restaurant")

    if request.method == "POST":
        form = MunchLogItemForm(request.POST, request.FILES)
        if form.is_valid():
            # Verify user owns the selected munch log
            if form.cleaned_data["munch_log"].owner != request.user:
                raise PermissionDenied

            munch_log_item = form.save()

            # Handle image upload if provided
            image_file = form.cleaned_data.get("image")
            if image_file:
                restaurant_image = RestaurantImage.objects.create(
                    restaurant=munch_log_item.restaurant,
                    image=image_file,
                    added_by=request.user,
                )
                munch_log_item.image = restaurant_image
                munch_log_item.save()

            messages.success(
                request, f'"{munch_log_item.restaurant.name}" added to your Munch Log!'
            )

            # Redirect based on where user came from
            if restaurant_id:
                return redirect(
                    "restaurant_detail", restaurant_id=munch_log_item.restaurant.id
                )
            else:
                return redirect("munch_log", user_id=request.user.id)
    else:
        # Initialize form with URL parameter values
        initial = {"munch_log": munch_log, "visited_date": timezone.now().date()}

        if restaurant_id:
            try:
                restaurant = Restaurant.objects.get(pk=restaurant_id)
                initial["restaurant"] = restaurant
            except Restaurant.DoesNotExist:
                pass

        form = MunchLogItemForm(initial=initial)

    # Get selected restaurant info for display
    selected_restaurant = None
    if restaurant_id:
        try:
            selected_restaurant = Restaurant.objects.get(pk=restaurant_id)
        except Restaurant.DoesNotExist:
            pass

    return render(
        request,
        "lists/munch_log_item_create.html",
        {
            "form": form,
            "munch_log": munch_log,
            "selected_restaurant_id": restaurant_id,
            "selected_restaurant": selected_restaurant,
        },
    )


@login_required
def munchlogitem_delete(request, item_id):
    """Delete a munch log item."""
    item = get_object_or_404(MunchLogItem, id=item_id)

    # Check if user owns the munch log
    if item.munch_log.owner != request.user:
        raise PermissionDenied

    restaurant_name = item.restaurant.name
    user_id = item.munch_log.owner.id
    item.delete()

    messages.success(request, f'"{restaurant_name}" removed from your Munch Log.')
    return redirect("munch_log", user_id=user_id)


@login_required
def edit_profile(request):
    """Edit user profile."""
    if request.method == "POST":
        form = EditProfileForm(request.POST, instance=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, "Your profile has been updated.")
            return redirect("profile", user_id=request.user.id)
    else:
        form = EditProfileForm(instance=request.user)

    return render(request, "lists/edit_profile.html", {"form": form})


@login_required
def restaurantlistitem_update(request, item_id):
    """Update a restaurant list item's notes."""
    item = get_object_or_404(RestaurantListItem, id=item_id)

    # Check if user owns the list
    if item.restaurant_list.owner != request.user:
        raise PermissionDenied

    if request.method == "POST":
        # Update notes
        item.notes = request.POST.get("notes", "")
        item.save()
        messages.success(request, f'Updated "{item.restaurant.name}" successfully!')

    return redirect("restaurantlist_edit", list_id=item.restaurant_list.id)


@login_required
def munchlogitem_update(request, item_id):
    """Update a munch log item's notes, visited date, and image."""
    item = get_object_or_404(MunchLogItem, id=item_id)

    # Check if user owns the munch log
    if item.munch_log.owner != request.user:
        raise PermissionDenied

    if request.method == "POST":
        form = MunchLogItemUpdateForm(request.POST, request.FILES, instance=item)
        if form.is_valid():
            form.save()

            # Handle image upload if provided
            image_file = form.cleaned_data.get("image")
            if image_file:
                restaurant_image = RestaurantImage.objects.create(
                    restaurant=item.restaurant,
                    image=image_file,
                    added_by=request.user,
                )
                item.image = restaurant_image
                item.save()

            messages.success(request, f'Updated "{item.restaurant.name}" successfully!')
            return redirect("munch_log", user_id=item.munch_log.owner.id)
        else:
            messages.error(request, "Please correct the errors below.")
    else:
        form = MunchLogItemUpdateForm(instance=item)

    return render(
        request,
        "lists/munch_log_item_edit.html",
        {"item": item, "form": form},
    )


@login_required
def restaurant_reimport(request, restaurant_id):
    """Reimport restaurant data from Nominatim Lookup API."""
    restaurant = get_object_or_404(Restaurant, id=restaurant_id)

    if request.method == "POST":
        try:
            # Validate OSM type
            if restaurant.osm_type not in [
                choice[0] for choice in Restaurant.OSMType.choices
            ]:
                raise ValueError(f"Invalid OSM type in database: {restaurant.osm_type}")

            # Fetch updated data from Nominatim
            data = fetch_restaurant_data_from_nominatim(
                restaurant.osm_type, restaurant.osm_id
            )

            # Update restaurant fields
            for field, value in data.items():
                setattr(restaurant, field, value)
            restaurant.save()

            messages.success(
                request,
                f'Restaurant "{restaurant.name}" data has been refreshed from OpenStreetMap!',
            )
        except Exception as e:
            messages.error(request, f"Error reimporting restaurant data: {str(e)}")

        return redirect("restaurant_detail", restaurant_id=restaurant.id)

    # For GET requests, redirect back to detail page
    return redirect("restaurant_detail", restaurant_id=restaurant.id)


@login_required
def add_by_node_id(request):
    """Add restaurant by OSM node ID directly."""
    if request.method == "POST":
        osm_id = request.POST.get("osm_id", "").strip()

        if not osm_id:
            messages.error(request, "Please enter an OSM node ID.")
            return render(request, "lists/add_by_node_id.html")

        # Validate that it's a number
        try:
            int(osm_id)
        except ValueError:
            messages.error(request, "OSM node ID must be a number.")
            return render(request, "lists/add_by_node_id.html", {"osm_id": osm_id})

        try:
            # Check if restaurant already exists
            try:
                existing_restaurant = Restaurant.objects.get(
                    osm_type=Restaurant.OSMType.NODE, osm_id=osm_id
                )
            except Restaurant.DoesNotExist:
                existing_restaurant = None

            if existing_restaurant:
                messages.info(
                    request,
                    f'"{existing_restaurant.name}" already exists in MunchZone. Redirecting to "{existing_restaurant.name}".',
                )
                return redirect(
                    "restaurant_detail", restaurant_id=existing_restaurant.id
                )

            # Create restaurant from OSM node
            restaurant = create_restaurant_from_osm(
                Restaurant.OSMType.NODE, osm_id, added_by=request.user
            )
            messages.success(
                request, f'Restaurant "{restaurant.name}" added to database!'
            )
            return redirect("restaurant_detail", restaurant_id=restaurant.id)

        except Exception as e:
            messages.error(request, f"Error adding restaurant: {str(e)}")
            return render(request, "lists/add_by_node_id.html", {"osm_id": osm_id})

    return render(request, "lists/add_by_node_id.html")


# ============================================================================
# Restaurant Creation (with OSM node creation)
# ============================================================================


@login_required
def restaurant_create(request):
    """Search for a restaurant via Gemini and confirm to create."""
    form = RestaurantCreateForm()
    return render(request, "lists/restaurant_create.html", {"form": form})


@login_required
def gemini_search_api(request):
    """AJAX endpoint for searching restaurants via Gemini with Google Maps grounding."""
    query = request.GET.get("q", "").strip()
    lat = request.GET.get("lat")
    lon = request.GET.get("lon")

    if not query:
        return JsonResponse({"error": "Query required"}, status=400)

    try:
        latitude = float(lat) if lat else None
        longitude = float(lon) if lon else None
    except (TypeError, ValueError):
        latitude = None
        longitude = None

    try:
        details = get_restaurant_details_from_gemini(query, latitude, longitude)
        if details:
            return JsonResponse({"result": details.model_dump()})
        else:
            return JsonResponse({"result": None, "message": "Restaurant not found"})
    except Exception:
        logger.exception("Gemini search error")
        return JsonResponse({"error": "Search failed"}, status=500)


@login_required
@require_POST
def restaurant_create_verify(request):
    """Show verification page with raw XML, or submit if confirmed."""
    form = RestaurantCreateForm(request.POST)
    if not form.is_valid():
        messages.error(request, "Invalid form data.")
        return redirect("restaurant_create")

    # Check if user has OSM account linked
    try:
        osm_account = request.user.osm_account
    except OsmAccount.DoesNotExist:
        messages.error(request, "Please connect your OpenStreetMap account first.")
        request.session["osm_connect_next"] = "restaurant_create"
        return redirect("osm_connect")

    data = form.cleaned_data

    # If "confirm" is in POST, actually create the node
    if "confirm" in request.POST:
        try:
            node_id = create_restaurant_node(
                access_token=osm_account.access_token,
                data=data,
            )
        except OsmAuthError:
            osm_account.delete()
            messages.warning(
                request,
                "Your OpenStreetMap authorization was revoked. Please reconnect your account.",
            )
            request.session["osm_connect_next"] = "restaurant_create"
            return redirect("osm_connect")

        restaurant = create_restaurant_from_osm(
            Restaurant.OSMType.NODE, str(node_id), added_by=request.user
        )
        messages.success(
            request,
            f'Restaurant "{restaurant.name}" created in OpenStreetMap and added to Munchzone!',
        )
        return redirect("restaurant_detail", restaurant_id=restaurant.id)

    # Otherwise, show the verification page
    tags = build_restaurant_tags(data)
    node_xml = build_node_xml(data["latitude"], data["longitude"], tags)

    return render(
        request,
        "lists/restaurant_create_verify.html",
        {
            "form": form,
            "node_xml": node_xml,
            "osm_api_url": settings.OSM_API_URL,
        },
    )


# ============================================================================
# OSM OAuth 2.0 Flow
# ============================================================================


@login_required
def osm_connect(request):
    """Initiate OAuth 2.0 flow with OpenStreetMap."""
    client_id = settings.OSM_OAUTH_CLIENT_ID
    if not client_id:
        messages.error(
            request,
            "OSM OAuth is not configured. Please set OSM_OAUTH_CLIENT_ID in settings.",
        )
        return redirect("profile", user_id=request.user.id)

    # Build callback URL
    callback_url = request.build_absolute_uri("/osm/callback/")

    # Create OAuth session
    oauth = OAuth2Session(
        client_id,
        redirect_uri=callback_url,
        scope=["write_api"],
    )

    # Get authorization URL
    authorization_url, state = oauth.authorization_url(
        "https://www.openstreetmap.org/oauth2/authorize"
    )

    # Store state in session for verification
    request.session["oauth_state"] = state

    return redirect(authorization_url)


@login_required
def osm_callback(request):
    """Handle OAuth 2.0 callback from OpenStreetMap."""
    client_id = settings.OSM_OAUTH_CLIENT_ID
    client_secret = settings.OSM_OAUTH_CLIENT_SECRET

    if not client_id or not client_secret:
        messages.error(request, "OSM OAuth is not configured.")
        return redirect("profile", user_id=request.user.id)

    # Verify state
    state = request.session.get("oauth_state")
    if not state:
        messages.error(request, "Invalid OAuth state. Please try again.")
        return redirect("osm_connect")

    # Build callback URL
    callback_url = request.build_absolute_uri("/osm/callback/")

    # Create OAuth session and fetch token
    oauth = OAuth2Session(client_id, redirect_uri=callback_url, state=state)
    token = oauth.fetch_token(
        "https://www.openstreetmap.org/oauth2/token",
        client_secret=client_secret,
        authorization_response=request.build_absolute_uri(),
    )

    # Create or update OsmAccount
    OsmAccount.objects.update_or_create(
        user=request.user,
        defaults={"access_token": token["access_token"]},
    )

    # Clear OAuth state
    del request.session["oauth_state"]

    messages.success(request, "Connected to OpenStreetMap!")

    # Redirect to next URL if set
    next_url = request.session.pop("osm_connect_next", None)
    if next_url:
        return redirect(next_url)

    return redirect("profile", user_id=request.user.id)


@login_required
@require_POST
def osm_disconnect(request):
    """Disconnect OSM account."""
    try:
        osm_account = request.user.osm_account
        osm_account.delete()
        messages.success(request, "Disconnected from OpenStreetMap.")
    except OsmAccount.DoesNotExist:
        pass

    return redirect("profile", user_id=request.user.id)
