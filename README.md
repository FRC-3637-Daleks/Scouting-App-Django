# Scouting-App-Django
Team 3637 scouting app for the 2024 FRC game FIRST CRESCENDO!

## Command line utilities

### The Blue Alliance Data Import

1. Setup the game and event in the django admin web panel `/admin`
2. Ensure the current event is marked as active in the admin panel, and the tba event key is correct (ex. `2024pahat`)
3. Check The Blue Alliance page for the event to see what is listed, it may be just teams, or teams and qualification matches
4. Open a command line with python virtual environment activated
5. Type the command `python manage.py sync_teams_matches_tba`
6. This will import the teams and matches (if available) from the blue alliance website

### Sync Stands Scouting Match Data

1. Ensure the stands server is running the same event as the pit server
2. Ensure the pit server URL is set correctly in settings.py on the stands server
3. Type the command `python manage.py sync_match_data` with an activated virtual environment
4. You should get a message indicating successful data transfer

### Sync Pit Scouting Data

1. Ensure the stands server is running the same event as the pit server
2. Ensure the pit server URL is set correctly in settings.py on the stands server
3. Type the command `python manage.py sync_pit_data` with an activated virtual environment
4. You should get a message indicating successful data transfer