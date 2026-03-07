from django.db import models
from django_extensions.db.models import TimeStampedModel
from django.conf import settings
import os
import uuid


def unique_pit_image_path(instance, filename):
    ext = os.path.splitext(filename)[1].lower()
    return f"images/{uuid.uuid4().hex}{ext}"


def unique_team_logo_path(instance, filename):
    ext = os.path.splitext(filename)[1].lower() or ".png"
    return f"team_logos/{instance.team_number}_{uuid.uuid4().hex}{ext}"


class Game(TimeStampedModel):
    year = models.IntegerField(unique=True)
    name = models.CharField(max_length=20)

    def __str__(self):
        return str(self.year) + " " + self.name


class Team(TimeStampedModel):
    team_name = models.CharField(max_length=30)
    team_number = models.IntegerField()
    team_logo = models.ImageField(upload_to=unique_team_logo_path, blank=True, null=True)

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
    friendly_or_cool = models.BooleanField(default=False)
    crisp_boompers = models.BooleanField(default=False)
    can_robot_l3_climb = models.BooleanField(default=False)
    can_robot_l1_climb = models.BooleanField(default=False)
    can_robot_l1_climb_in_auto = models.BooleanField(default=False)
    can_robot_drive_under_trench = models.BooleanField(default=False)

    # Integer Fields

    # Char Fields
    intake_type = models.CharField(max_length=100, null=True)
    type_drivebase= models.CharField(max_length=100, null=True)
    auton_paths_or_description= models.TextField(max_length=1000, null=True)
    description = models.TextField(max_length=2000)
    #Image Fields
    auton_picture_1 = models.ImageField(upload_to=unique_pit_image_path, blank=True, null=True)
    auton_picture_2 = models.ImageField(upload_to=unique_pit_image_path, blank=True, null=True)
    auton_picture_3 = models.ImageField(upload_to=unique_pit_image_path, blank=True, null=True)
    robot_picture_1 = models.ImageField(upload_to=unique_pit_image_path, blank=True, null=True)
    robot_picture_2 = models.ImageField(upload_to=unique_pit_image_path, blank=True, null=True)

    class Meta:
        verbose_name_plural = "Pit scout data"
        permissions = (
            ("pit_scout_teams", "Can pit scout teams"),
        )

    def __str__(self):
        return str(str(self.team.team_number) + " - " + self.team.team_name + " | " + self.event.event_name)

class TeamRanking(models.Model):
    team = models.ForeignKey(Team, on_delete=models.CASCADE, related_name='teamranking')
    event = models.ForeignKey(Event, on_delete=models.CASCADE)
    rank = models.IntegerField(null=True, blank=True)
    priority = models.FloatField(null=True, blank=True)
    opr = models.FloatField(default=0.0)
    dpr = models.FloatField(default=0.0)
    ccwm = models.FloatField(default=0.0)
    auto_tower_points = models.FloatField(default=0.0)
    total_auto_points = models.FloatField(default=0.0)
    total_teleop_points = models.FloatField(default=0.0)
    endgame_tower_points = models.FloatField(default=0.0)
    total_tower_points = models.FloatField(default=0.0)

    hub_auto_fuel_count = models.FloatField(default=0.0)
    hub_teleop_fuel_count = models.FloatField(default=0.0)
    hub_endgame_fuel_count = models.FloatField(default=0.0)
    hub_total_fuel_count = models.FloatField(default=0.0)
    hub_transition_fuel_count = models.FloatField(default=0.0)
    hub_shift_1_fuel_count = models.FloatField(default=0.0)
    hub_shift_2_fuel_count = models.FloatField(default=0.0)
    hub_shift_3_fuel_count = models.FloatField(default=0.0)
    hub_shift_4_fuel_count = models.FloatField(default=0.0)

    energized_achieved = models.FloatField(default=0.0)
    supercharged_achieved = models.FloatField(default=0.0)
    traversal_achieved = models.FloatField(default=0.0)
    minor_foul_count = models.FloatField(default=0.0)
    major_foul_count = models.FloatField(default=0.0)
    foul_points = models.FloatField(default=0.0)
    g206_penalty = models.FloatField(default=0.0)
    alliance_number = models.IntegerField(default=0)
    copr_breakdown = models.JSONField(default=dict, blank=True)

    class Meta:
        unique_together = ('team', 'event')

class MatchData2026(TimeStampedModel):
    team = models.ForeignKey('Team', on_delete=models.CASCADE, null=False)
    match = models.ForeignKey('Match', on_delete=models.CASCADE, null=False)


    @property
    def event(self):
        return self.match.event_id

    #Match Tags
    #integers

    #strings
    #starting_location = models.CharField(max_length=20, null=True)
    defense_effectiveness = models.CharField(max_length=1000, null=True)
    scoring_accuracy_or_effectiveness = models.CharField(max_length=1000, null=True)
    human_player_accuracy = models.CharField(max_length=1000, null=True)
    compatibility_with_alliance_members = models.CharField(max_length=1000, null=True)
    other_comments = models.CharField(max_length=1000, null=True)
    tower_climb_time = models.IntegerField(null=True, blank=True)




    class Meta:
        permissions = (
            ("stands_scout_team", "Can stands scout teams"),
        )

