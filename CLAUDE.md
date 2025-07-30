# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Munch is a Django 5.2.4 restaurant list management application where users can search for restaurants via the Nominatim API and organize them into personal lists.

## Development Commands

**IMPORTANT:** Always use `DJANGO_SETTINGS_MODULE=munch.dev_settings` when running Django commands in development.

**Start development server:**
```bash
DJANGO_SETTINGS_MODULE=munch.dev_settings uv run manage.py runserver
```

**Database migrations:**
```bash
DJANGO_SETTINGS_MODULE=munch.dev_settings uv run manage.py makemigrations
DJANGO_SETTINGS_MODULE=munch.dev_settings uv run manage.py migrate
```

**Note:** Apply migrations only when explicitly asked to do so. Running `makemigrations` to create migrations is OK.

**Create superuser:**
```bash
DJANGO_SETTINGS_MODULE=munch.dev_settings uv run manage.py createsuperuser
```

**Django shell:**
```bash
DJANGO_SETTINGS_MODULE=munch.dev_settings uv run manage.py shell
```

**Production deployment check:**
```bash
DJANGO_SETTINGS_MODULE=munch.settings SECRET_KEY=your-secret-key uv run manage.py check --deploy
```

**Build Tailwind CSS:**
```bash
npx @tailwindcss/cli -i ./lists/main.css -o ./lists/static/css/main.css --watch
```

**Install dependencies:**
```bash
uv install
npm install
```

**Run tests:**
```bash
DJANGO_SETTINGS_MODULE=munch.dev_settings uv run manage.py test
```

**Collect static files (production):**
```bash
uv run manage.py collectstatic
```

## Development Environment Setup

- **Environment Variable:** Always prefix Django commands with `DJANGO_SETTINGS_MODULE=munch.dev_settings` in development

## Architecture

### Custom User Model
- Uses `lists.User` which extends `AbstractUser` (transparent wrapper)
- Configured in settings: `AUTH_USER_MODEL = 'lists.User'`
- When creating forms that work with User model, extend Django's built-in forms:
  ```python
  class CustomUserCreationForm(UserCreationForm):
      class Meta(UserCreationForm.Meta):
          model = User
  ```

### Core Models
- **Restaurant**: Stores restaurant data with OpenStreetMap integration (osm_type, osm_id)
- **RestaurantImage**: Multiple images per restaurant with automatic file cleanup
- **RestaurantList**: User-owned lists of restaurants
- **RestaurantListItem**: Junction table linking restaurants to lists (allows duplicates)
- **MunchLog**: Personal restaurant log for each user (one-to-one with User)
- **MunchLogItem**: Individual entries in a user's Munch Log
- **ListComment**: Comments on restaurant lists
- **ListFollow**: User following relationships for restaurant lists

### Nominatim API Integration
- **Search**: Uses Nominatim Search API to find restaurants
- **Creation**: Uses Nominatim Lookup API to securely fetch restaurant details
- **OSM Types**: Enum-based system mapping `node`/`way`/`relation` to `N`/`W`/`R`
- **Security**: Client only submits OSM type/ID, server fetches all other data

Key function: `create_restaurant_from_osm(osm_type: OSMType, osm_id)` - takes enum and ID, calls Nominatim Lookup API, creates Restaurant object.

### Template Structure
- **Base template**: `base.html` with navigation (shows login/logout based on auth status)
- **Authentication**: Uses Django's built-in auth views at `/accounts/`
- **Templates**: All extend base template using `{% extends 'base.html' %}` pattern

### URL Structure
- Main URLs in `munch/urls.py` include Django auth URLs and lists app
- Lists app URLs handle all restaurant/list management functionality
- Authentication routes: `/accounts/login/`, `/accounts/logout/`, `/register/`

## Key Implementation Details

### Restaurant Creation Flow
1. User searches via Nominatim Search API
2. Results displayed with OSM type/ID
3. User clicks "Add to Database" 
4. Form submits only OSM type/ID
5. Server calls Nominatim Lookup API to get full restaurant data
6. Restaurant created with validated data

### Database Schema
- Users own RestaurantLists
- RestaurantListItems link restaurants to lists
- Restaurants store OSM data for re-lookup capability
- All models use `inserted_at` for timestamps (not Django's default `created_at`)
- **Duplicate entries are allowed**: The same restaurant can be added to the same list multiple times

### Form Patterns
- ModelForms for database objects
- Custom forms for API interactions (like RestaurantForm with hidden OSM fields)
- Always extend Django's built-in forms when working with User model

## Technical Details

### Database Configuration
- PostgreSQL with PostGIS extension for geographic data
- Database name: `munch`, user: `munch`, no password, localhost:5432
- Uses Django GIS with PointField for restaurant locations

### Dependencies
- **Python**: Requires Python 3.13+, managed with `uv`
- **Core**: Django 5.2.4+, Pillow 11.3.0+, psycopg[binary] 3.2.9+
- **Frontend**: Tailwind CSS 4.1.11 via npm

### File Handling
- Media files stored in `media/` directory
- Restaurant images uploaded to `media/restaurants/`
- Automatic file cleanup via Django signals when images are deleted/replaced

### Frontend Architecture
- Tailwind CSS for styling with utility-first approach
- Leaflet.js for interactive maps
- Fixed design for mobile phone in portrait orientation
- Templates use Django's template inheritance pattern
- Accessibility: alt-text for images, screen reader compatibility

## Social Features
- **List Following**: Users can follow other users' restaurant lists
- **Comments**: Users can comment on restaurant lists
- **Activity Feed**: Home page shows recent activity from followed lists and munch log entries
- **Munch Log**: Each user has a personal restaurant log (auto-created via `get_or_create_munch_log()`)

## API Endpoints
- **Restaurant Search API**: `/api/restaurant/search/` - AJAX endpoint for restaurant autocomplete
- **Nominatim Integration**: External API calls to OpenStreetMap Nominatim service
  - Search API: For finding restaurants by query
  - Lookup API: For fetching complete restaurant details by OSM ID

## Testing
- **Test Framework**: Django's built-in TestCase
- **Current Status**: Minimal test coverage (tests.py contains only boilerplate)
- **Run Tests**: `DJANGO_SETTINGS_MODULE=munch.dev_settings uv run manage.py test`

## File Structure & Important Patterns
- **Signal Handlers**: Automatic file cleanup for RestaurantImage deletions (models.py)
- **Custom Timestamps**: All models use `inserted_at` instead of Django's default `created_at`
- **Geographic Data**: Restaurant locations stored as PostGIS Point fields
- **Form Validation**: OSM type/ID validation in RestaurantForm for security
- **Template Inheritance**: All templates extend `base.html` with consistent navigation

## Development Workflow
- **Package Management**: `uv` for Python dependencies, `npm` for frontend
- **CSS Build Process**: Tailwind CSS compilation required for styling changes
- **Database**: PostgreSQL with PostGIS extension for geographic features
- **Static Files**: Collected to `staticfiles/` directory for production
- **Media Files**: User uploads stored in `media/` directory with automatic cleanup
