from django.db import models
from django_extensions.db.models import TimeStampedModel
from django.conf import settings


class Game(TimeStampedModel):
    year = models.IntegerField(unique=True)
    name = models.CharField(max_length=20)

    def __str__(self):
        return str(self.year) + " " + self.name


class Team(TimeStampedModel):
    team_name = models.CharField(max_length=30)
    team_number = models.IntegerField()

    def __str__(self):
        return str(self.team_number) + " - " + self.team_name


class Event(TimeStampedModel):
    game = models.ForeignKey(Game, on_delete=models.CASCADE)
    event_name = models.CharField(max_length=30)
    start_date = models.DateField()
    end_date = models.DateField()
    active = models.BooleanField(default=False)
    tba_event_key = models.CharField(max_length=20, null=True)
    teams = models.ManyToManyField(Team, blank=True)

    def save(self, *args, **kwargs):
        if self.active:
            Event.objects.filter(active=True).update(active=False)
        super(Event, self).save(*args, **kwargs)

    def __str__(self):
        return str(self.game.year) + " " + self.event_name


class Match(TimeStampedModel):
    match_number = models.IntegerField()
    event_id = models.ForeignKey(Event, on_delete=models.CASCADE, null=False, related_name="+")
    team_red_1 = models.ForeignKey(Team, on_delete=models.CASCADE, null=False, related_name="+")
    team_red_2 = models.ForeignKey(Team, on_delete=models.CASCADE, null=False, related_name="+")
    team_red_3 = models.ForeignKey(Team, on_delete=models.CASCADE, null=False, related_name="+")
    team_blue_1 = models.ForeignKey(Team, on_delete=models.CASCADE, null=False, related_name="+")
    team_blue_2 = models.ForeignKey(Team, on_delete=models.CASCADE, null=False, related_name="+")
    team_blue_3 = models.ForeignKey(Team, on_delete=models.CASCADE, null=False, related_name="+")

    class Meta:
        verbose_name_plural = "Matches"

    def __str__(self):
        return str(self.match_number)


class TbaApiKey(models.Model):
    api_key = models.CharField(max_length=100, null=False, blank=False)
    active = models.BooleanField(default=False)

    class Meta:
        verbose_name_plural = "The Blue Alliance API Keys"

    def save(self, *args, **kwargs):
        if self.active:
            TbaApiKey.objects.filter(active=True).update(active=False)
        super(TbaApiKey, self).save(*args, **kwargs)


class PitScoutData(TimeStampedModel):
    team = models.ForeignKey('Team', on_delete=models.CASCADE, null=False, blank=False)
    event = models.ForeignKey('Event', on_delete=models.CASCADE, null=False)
    assigned_scout = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)
    # Boolean Fields
    has_crisp_boombers = models.BooleanField(default=False, name='Crisp Boombers')
    has_floor_pickup = models.BooleanField(default=False, name='Floor Pickup')
    has_player_station_pickup = models.BooleanField(default=False, name='Player Station Pickup')
    can_go_under_stage = models.BooleanField(default=False, name='Can go under stage')
    has_april_tag_recognition = models.BooleanField(default=False, name='April Tag Recognition')
    has_vision_object_detection = models.BooleanField(default=False, name='Can detect obstacles with vision processing')
    has_variable_angle_shooter = models.BooleanField(default=False, name='Variable Angle Shooter')
    can_climb = models.BooleanField(default=False, name='Climb')
    can_climb_2_robots = models.BooleanField(default=False, name='Climb with another robot')
    can_lift_another_robot = models.BooleanField(default=False, name='Can lift another robot')
    can_score_amp = models.BooleanField(default=False, name='Can score in amp')
    shoots_up_into_amp = models.BooleanField(default=False, name='Shoots upwards into amp')
    shoots_down_into_amp = models.BooleanField(default=False ,name='Shoots downwards into amp')
    can_score_speaker_from_subwoofer = models.BooleanField(default=False, name='Can score in speaker from subwoofer')
    can_score_speaker_from_other_position = models.BooleanField(default=False, name='Can score in speaker from elsewhere on field')
    can_place_note_in_trap = models.BooleanField(default=False, name='Can place note in trap')
    # Integer Fields
    linear_speed = models.IntegerField(default=0, name='Linear speed, (meters per second)')
    robot_length_in = models.IntegerField(default=0 ,name='Robot length (inches)')
    robot_width_in = models.IntegerField(default=0, name='Robot width (inches)')
    robot_height_in = models.IntegerField(default=0, name='Robot height (inches)')
    robot_weight_lbs = models.IntegerField(default=0, name='Robot weight (lbs)')
    # Char Fields
    description = models.TextField(max_length=2000)

    class Meta:
        verbose_name_plural = "Pit scout data"
        permissions = (
            ("pit_scout_teams", "Can pit scout teams"),
        )

    def __str__(self):
        return str(str(self.team.team_number) + " - " + self.team.team_name + " | " + self.event.event_name)


class MatchData2024(TimeStampedModel):
    team = models.ForeignKey('Team', on_delete=models.CASCADE, null=False)
    match = models.ForeignKey('Match', on_delete=models.CASCADE, null=False)

    @property
    def event(self):
        return self.match.event_id

    # Pre-Match Tags
    #bools
    arrived_on_field_on_time = models.BooleanField(default=True)
    start_with_note = models.BooleanField(default=False)
    dead_on_arrival = models.BooleanField(default=False)
    #strings
    starting_location = models.CharField(max_length=20, null=True)

    # Auton Tags
    #bools
    left_community_zone = models.BooleanField(default=False)
    a_stopped = models.BooleanField(default=False)
    #ints
    auton_amp_notes_scored = models.IntegerField(default=0)
    auton_speaker_notes_scored = models.IntegerField(default=0)
    auton_notes_picked_up = models.IntegerField(default=0)

    # Teleop Tags
    #bools
    e_stopped = models.BooleanField(default=False)
    communication_lost= models.BooleanField(default=False)
    #ints
    teleop_speaker_notes_scored = models.IntegerField(default=0)
    teleop_amp_notes_scored = models.IntegerField(default=0)
    teleop_notes_missed = models.IntegerField(default=0)

    # Endgame Tags
    #bools
    climbed_solo = models.BooleanField(default=False)
    climbed_with_another_robot = models.BooleanField(default=False)
    scored_high_notes = models.BooleanField(default=False)
    #integer
    notes_scored_in_trap = models.IntegerField(default=0)
    comments = models.TextField(max_length=1000, null=True, blank=True)
    class Meta:
        permissions = (
            ("stands_scout_team", "Can stands scout teams"),
        )