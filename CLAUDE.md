# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Munch is a Django restaurant list management application where users can search for restaurants via the OpenStreetMap Nominatim API and organize them into personal lists. Production site: munchzone.net

## Development Commands

**IMPORTANT:** Always use `DJANGO_SETTINGS_MODULE=munch.dev_settings` when running Django commands in development.

```bash
# Start development server
DJANGO_SETTINGS_MODULE=munch.dev_settings uv run manage.py runserver

# Database migrations (only apply when explicitly asked)
DJANGO_SETTINGS_MODULE=munch.dev_settings uv run manage.py makemigrations
DJANGO_SETTINGS_MODULE=munch.dev_settings uv run manage.py migrate

# Django shell (interactive)
DJANGO_SETTINGS_MODULE=munch.dev_settings uv run manage.py shell

# Run Python code in Django context (use this instead of `uv run python -c`)
DJANGO_SETTINGS_MODULE=munch.dev_settings uv run manage.py shell -c "from lists.models import Restaurant; print(Restaurant.objects.count())"

# Run tests
DJANGO_SETTINGS_MODULE=munch.dev_settings uv run manage.py test

# Build Tailwind CSS (run in separate terminal)
npx @tailwindcss/cli -i ./lists/main.css -o ./lists/static/css/main.css --watch

# Install dependencies
uv sync
npm install
```

## Architecture

### Custom User Model
- Uses `lists.User` extending `AbstractUser` (transparent wrapper)
- Configured via `AUTH_USER_MODEL = 'lists.User'`
- When creating User forms, extend Django's built-in forms:
  ```python
  class CustomUserCreationForm(UserCreationForm):
      class Meta(UserCreationForm.Meta):
          model = User
  ```

### Core Models
- **Restaurant**: OSM-backed restaurant data (`osm_type` N/W/R + `osm_id`), with PointField location and `added_by` tracking
- **RestaurantImage**: Multiple images per restaurant with automatic file cleanup via signals
- **RestaurantList**: User-owned lists with `blurb` description
- **RestaurantListItem**: Junction table (allows duplicate restaurants in same list)
- **MunchLog**: Personal restaurant log (one-to-one with User, auto-created via `get_or_create_munch_log()`)
- **MunchLogItem**: Individual munch log entries with `visited_date`
- **ListComment**: Comments on restaurant lists
- **ListFollow**: User following relationships for lists

### Nominatim API Integration (views.py)
- **Search API**: `restaurant_nominatim()` - searches Nominatim, displays results
- **Lookup API**: `fetch_restaurant_data_from_nominatim()` - fetches full details by OSM type/ID
- **Creation**: `create_restaurant_from_osm(osm_type, osm_id, added_by)` - creates Restaurant from OSM data
- **Reimport**: `restaurant_reimport()` - refreshes existing restaurant data from OSM
- **Security**: Client only submits OSM type/ID; server fetches all other data from Nominatim

### Database
- PostgreSQL with PostGIS extension
- Default: database `munch`, user `munch`, no password, localhost:5432
- All models use `created_at` timestamps (via `auto_now_add=True`)
- **Always ask before making database/model changes** (migrations, schema changes, new fields)

### Frontend
- Tailwind CSS (v4.x) for styling
- Leaflet.js for interactive maps
- Mobile-first design (portrait orientation)
- Templates extend `base.html`

## Key Patterns

### Restaurant Import Flow
1. User searches via Nominatim Search API (`/import/`)
2. Or enters OSM node ID directly (`/import/node-id/`)
3. Form submits only OSM type/ID
4. Server calls Nominatim Lookup API for full data
5. Restaurant created with `added_by` set to current user

### File Cleanup
Signal handlers in `models.py` automatically delete image files when `RestaurantImage` instances are deleted or updated.

### Foreign Key Constraints
Most FKs use `on_delete=models.RESTRICT` to prevent accidental data loss (User, Restaurant). Only junction tables use `CASCADE`.

## Code Style

Prioritize correctness and simplicity over performance. The database is small and will remain so for the foreseeable future—don't add indexes, caching, or other optimizations unless there's a demonstrated need. Simple, readable code that's obviously correct is more valuable than clever code that's theoretically faster.

Don't add defensive checks for conditions that can't happen (e.g., checking for null on a non-nullable field). They obscure what can actually fail and make the code harder to reason about.

## API Endpoints
- `/api/restaurant/search/` - AJAX autocomplete for restaurants (min 2 chars)
