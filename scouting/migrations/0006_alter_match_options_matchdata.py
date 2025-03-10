# Generated by Django 5.0.2 on 2024-02-15 04:30

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('scouting', '0005_alter_game_auton_fields_alter_game_endgame_fields_and_more'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='match',
            options={'verbose_name_plural': 'Matches'},
        ),
        migrations.CreateModel(
            name='MatchData',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('match', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='+', to='scouting.match')),
                ('team', models.ForeignKey(limit_choices_to=models.Q(('matchdata__match__team_red_1', models.F('id')), ('matchdata__match__team_red_2', models.F('id')), ('matchdata__match__team_red_3', models.F('id')), ('matchdata__match__team_blue_1', models.F('id')), ('matchdata__match__team_blue_2', models.F('id')), ('matchdata__match__team_blue_3', models.F('id')), _connector='OR'), on_delete=django.db.models.deletion.CASCADE, related_name='+', to='scouting.team')),
            ],
        ),
    ]
