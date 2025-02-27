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
    friendly= models.BooleanField(default=False)
    crisp_boomers = models.BooleanField(default=False)

    # Integer Fields

    # Char Fields
    intake_type = models.CharField(max_length=100, null=True)
    type_drivebase= models.CharField(max_length=100, null=True)
    auton_paths= models.CharField(max_length=1000, null=True)
    description = models.TextField(max_length=2000)
    #Image Fields
    auton_picture = models.ImageField(upload_to='images/', null=True)
    robot_picture = models.ImageField(upload_to='images/', null=True)

    class Meta:
        verbose_name_plural = "Pit scout data"
        permissions = (
            ("pit_scout_teams", "Can pit scout teams"),
        )

    def __str__(self):
        return str(str(self.team.team_number) + " - " + self.team.team_name + " | " + self.event.event_name)

class TeamRanking(models.Model):
    team = models.ForeignKey(Team, on_delete=models.CASCADE)
    event = models.ForeignKey(Event, on_delete=models.CASCADE)
    rank = models.IntegerField()
    priority = models.IntegerField(null=True, blank=True)
    ranking_score = models.FloatField()
    matches_played = models.IntegerField()
    opr = models.FloatField(default=0.0)
    dpr = models.FloatField(default=0.0)
    ccwm = models.FloatField(default=0.0)
    l1_coral = models.FloatField(default=0.0)
    l2_coral = models.FloatField(default=0.0)
    l3_coral = models.FloatField(default=0.0)
    l4_coral = models.FloatField(default=0.0)
    net_algae_count = models.FloatField(default=0.0)
    wall_algae_count = models.FloatField(default=0.0)
    auto_coral_count = models.FloatField(default=0.0)
    foul_count = models.FloatField(default=0.0)
    class Meta:
        unique_together = ('team', 'event')
class MatchData2025(TimeStampedModel):
    team = models.ForeignKey('Team', on_delete=models.CASCADE, null=False)
    match = models.ForeignKey('Match', on_delete=models.CASCADE, null=False)

    @property
    def event(self):
        return self.match.event_id

    #Match Tags
    #integers

    #strings
    #starting_location = models.CharField(max_length=20, null=True)
    defense_text = models.CharField(max_length=1000, null=True)
    counter_defense_text = models.CharField(max_length=1000, null=True)
    human_player = models.CharField(max_length=1000, null=True)
    compatibility = models.CharField(max_length=1000, null=True)
    other_comments = models.CharField(max_length=1000, null=True)



    class Meta:
        permissions = (
            ("stands_scout_team", "Can stands scout teams"),
        )