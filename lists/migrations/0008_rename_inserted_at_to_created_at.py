# Generated by Django 5.2.4 on 2025-07-31 11:42

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('lists', '0007_restaurant_added_by_restaurant_inserted_at'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='listcomment',
            options={'ordering': ['-created_at']},
        ),
        migrations.AlterModelOptions(
            name='munchlogitem',
            options={'ordering': [models.OrderBy(models.F('visited_date'), descending=True, nulls_last=True), '-created_at']},
        ),
        migrations.AlterModelOptions(
            name='restaurantlist',
            options={'ordering': ['-created_at']},
        ),
        migrations.RemoveIndex(
            model_name='listcomment',
            name='lists_listc_restaur_308f10_idx',
        ),
        migrations.RenameField(
            model_name='listcomment',
            old_name='inserted_at',
            new_name='created_at',
        ),
        migrations.RenameField(
            model_name='munchlogitem',
            old_name='inserted_at',
            new_name='created_at',
        ),
        migrations.RenameField(
            model_name='restaurant',
            old_name='inserted_at',
            new_name='created_at',
        ),
        migrations.RenameField(
            model_name='restaurantlist',
            old_name='inserted_at',
            new_name='created_at',
        ),
        migrations.RenameField(
            model_name='restaurantlistitem',
            old_name='inserted_at',
            new_name='created_at',
        ),
        migrations.AddIndex(
            model_name='listcomment',
            index=models.Index(fields=['restaurant_list', '-created_at'], name='lists_listc_restaur_d668d1_idx'),
        ),
    ]
