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

## Setup app

### Development

#### Step 1
goto whatever directory and open CMD    <br>
`python -m venv ScoutingApp`            <br>

#### Step 2                             <br>
`cd into ScoutingApp`                   <br>
`cd ScoutingApp`                        <br>
make sure you have git installed        <br>
`git clone -b whatever_brach_you_want_to_clone https://github.com/FRC-3637-Daleks/Scouting-App-Django.git`  <br>

#### Step 3                             <br>
Activate venv                           <br>
`.\Scripts\activate.bat`                <br>

#### Step 4
install django                          <br>
`pip install django`                    <br>
`pip3 install djangorestframework`      <br>
`pip install django-crispy-forms`       <br>
`pip install crispy-bootstrap5`         <br>
`pip install django-extensions`         <br>
`pip install requests`                  <br>

#### Step 5
Start the server                        <br>
`cd Scouting-App-Django`                <br>
`py manage.py runserver`                <br>
