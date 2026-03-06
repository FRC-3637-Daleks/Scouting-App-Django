# Scouting-App-Django

Team 3637 scouting app for the 2026 FRC game.

## Setup

### Prerequisites

- Python 3.12+
- pip

### Installation

```bash
# Clone the repository
git clone https://github.com/FRC-3637-Daleks/Scouting-App-Django.git
cd Scouting-App-Django

# Create and activate a virtual environment
python -m venv .venv

# Windows
.venv\Scripts\activate

# macOS/Linux
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Apply database migrations
python manage.py migrate

# Create a superuser account for the admin panel
python manage.py createsuperuser

# Start the development server
python manage.py runserver
```

The app will be running at `http://127.0.0.1:8000/`. The admin panel is at `/admin`.

## Admin Panel Setup

Before using the app at an event:

1. Go to `/admin` and log in with your superuser account
2. **Add a Game** — set the year (e.g. `2026`) and name
3. **Add an Event** — link it to the game, set the TBA event key (e.g. `2026pahat`), and mark it as **Active**
4. **Add a TBA API Key** — get one from [thebluealliance.com/account](https://www.thebluealliance.com/account), paste it in, and mark it as **Active**

## Management Commands

All commands require the virtual environment to be activated and should be run from the project root.

### Import Teams & Matches from TBA

```bash
python manage.py sync_teams_matches_tba
```

Imports teams and match schedule (if available) from The Blue Alliance for the active event.

### Sync OPR / DPR / CCWM

```bash
python manage.py sync_opr
```

Fetches OPR, DPR, and CCWM stats from TBA for the active event.

### Sync Component OPRs (COPRs)

```bash
python manage.py sync_copr
```

Fetches Component OPRs (tower points, hub fuel counts, foul stats, etc.) from TBA for the active event.

### Sync Rankings

```bash
python manage.py sync_rank
```

Fetches team rankings from TBA for the active event.

### Sync Stands Scouting Match Data

```bash
python manage.py sync_match_data
```

Syncs stands scouting data from a remote server. Requires `SYNC_MASTER_SERVER` to be set in `settings.py`.

### Sync Pit Scouting Data

```bash
python manage.py sync_pit_data
```

Syncs pit scouting data from a remote server. Requires `SYNC_MASTER_SERVER` to be set in `settings.py`.

### Sync Priority Rankings

```bash
python manage.py sync_priority
```

Syncs team priority rankings from a remote server.