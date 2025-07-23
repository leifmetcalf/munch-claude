import os
from django.contrib.auth.models import AbstractUser
from django.contrib.gis.db import models
from django.contrib.gis.geos import Point
from django.db.models.signals import post_delete, pre_save
from django.dispatch import receiver


class User(AbstractUser):
    def get_or_create_munch_log(self):
        """Get or create the user's Munch Log."""
        munch_log, created = RestaurantList.objects.get_or_create(
            owner=self,
            is_munch_log=True,
            defaults={
                'name': f"{self.username}'s Munch Log",
                'blurb': "My personal log of restaurant visits and food adventures!"
            }
        )
        return munch_log


class Restaurant(models.Model):
    name = models.CharField(max_length=200)
    address = models.CharField(max_length=300)
    suburb = models.CharField(max_length=100)
    region = models.CharField(max_length=100)
    country = models.CharField(max_length=100)
    osm_type = models.CharField(max_length=20)
    osm_id = models.CharField(max_length=20)
    location = models.PointField(help_text="Geographic location from Nominatim")
    
    class Meta:
        unique_together = ['osm_type', 'osm_id']
    
    def __str__(self):
        return self.name


class RestaurantImage(models.Model):
    restaurant = models.ForeignKey(Restaurant, on_delete=models.CASCADE, related_name='images')
    image = models.ImageField(upload_to='restaurants/', help_text="Restaurant photo")
    alt_text = models.CharField(max_length=200, blank=True, help_text="Alt text for accessibility")
    added_by = models.ForeignKey(User, on_delete=models.CASCADE, help_text="User who added this image")
    uploaded_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['uploaded_at']
    
    def __str__(self):
        return f"Image for {self.restaurant.name}"


class RestaurantList(models.Model):
    name = models.CharField(max_length=200)
    owner = models.ForeignKey(User, on_delete=models.CASCADE)
    blurb = models.TextField(blank=True, help_text="Description or notes about this list")
    inserted_at = models.DateTimeField(auto_now_add=True)
    is_munch_log = models.BooleanField(default=False, help_text="Designates if this is the user's special Munch Log")
    
    class Meta:
        ordering = ['-inserted_at']
        constraints = [
            models.UniqueConstraint(
                fields=['owner', 'is_munch_log'],
                condition=models.Q(is_munch_log=True),
                name='unique_munch_log_per_user'
            )
        ]
    
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


@receiver(post_delete, sender=RestaurantImage)
def delete_restaurant_image_file(sender, instance, **kwargs):
    """Delete image file when RestaurantImage instance is deleted"""
    if instance.image:
        if os.path.isfile(instance.image.path):
            os.remove(instance.image.path)


@receiver(pre_save, sender=RestaurantImage)
def delete_old_restaurant_image(sender, instance, **kwargs):
    """Delete old image file when a new one is uploaded"""
    if not instance.pk:
        return False
    
    try:
        old_image = RestaurantImage.objects.get(pk=instance.pk).image
    except RestaurantImage.DoesNotExist:
        return False
    
    if old_image and old_image != instance.image:
        if os.path.isfile(old_image.path):
            os.remove(old_image.path)


class ListComment(models.Model):
    restaurant_list = models.ForeignKey(RestaurantList, on_delete=models.CASCADE, related_name='comments')
    author = models.ForeignKey(User, on_delete=models.CASCADE)
    content = models.TextField(max_length=1000, help_text="Comment about this restaurant list")
    inserted_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-inserted_at']  # Most recent first
        indexes = [
            models.Index(fields=['restaurant_list', '-inserted_at']),
        ]
    
    def __str__(self):
        return f"Comment by {self.author.username} on {self.restaurant_list.name}"


class ListFollow(models.Model):
    follower = models.ForeignKey(User, on_delete=models.CASCADE, related_name='following_lists')
    restaurant_list = models.ForeignKey(RestaurantList, on_delete=models.CASCADE, related_name='followers')
    followed_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        unique_together = ['follower', 'restaurant_list']  # Prevent duplicate follows
        ordering = ['-followed_at']  # Most recent first
        indexes = [
            models.Index(fields=['follower', '-followed_at']),
            models.Index(fields=['restaurant_list', '-followed_at']),
        ]
    
    def __str__(self):
        return f"{self.follower.username} follows {self.restaurant_list.name}"
