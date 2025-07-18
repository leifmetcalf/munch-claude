from django.contrib.auth.models import AbstractUser
from django.contrib.gis.db import models


class User(AbstractUser):
    pass


class Restaurant(models.Model):
    name = models.CharField(max_length=200)
    address = models.CharField(max_length=300)
    suburb = models.CharField(max_length=100)
    region = models.CharField(max_length=100)
    country = models.CharField(max_length=100)
    osm_type = models.CharField(max_length=20)
    osm_id = models.CharField(max_length=20)
    location = models.PointField(null=True, blank=True, help_text="Geographic location from Nominatim")
    
    class Meta:
        unique_together = ['osm_type', 'osm_id']
    
    def __str__(self):
        return self.name


class RestaurantList(models.Model):
    name = models.CharField(max_length=200)
    owner = models.ForeignKey(User, on_delete=models.CASCADE)
    inserted_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-inserted_at']
    
    def __str__(self):
        return self.name


class RestaurantListItem(models.Model):
    restaurant = models.ForeignKey(Restaurant, on_delete=models.CASCADE)
    restaurant_list = models.ForeignKey(RestaurantList, on_delete=models.CASCADE)
    inserted_at = models.DateTimeField(auto_now_add=True)
    order = models.PositiveIntegerField(default=0)
    notes = models.TextField(blank=True, help_text="Optional notes about this restaurant")
    
    class Meta:
        ordering = ['order']
    
    def __str__(self):
        return f"{self.restaurant.name} in {self.restaurant_list.name}"
