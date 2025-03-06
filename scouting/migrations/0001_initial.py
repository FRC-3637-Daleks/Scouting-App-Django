# Generated by Django 5.0.2 on 2024-02-15 04:07

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
    ]

    operations = [
        migrations.CreateModel(
            name='Game',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('year', models.IntegerField()),
                ('name', models.CharField(max_length=20)),
            ],
        ),
        migrations.CreateModel(
            name='MatchField',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('type', models.CharField(choices=[('BOOL', 'Bool'), ('INTEGER', 'Integer')], default='BOOL', max_length=7)),
                ('field_name', models.CharField(max_length=30)),
                ('field_value_bool', models.BooleanField(default=False)),
                ('field_value_integer', models.IntegerField(default=None)),
            ],
        ),
        migrations.CreateModel(
            name='Team',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('team_name', models.CharField(max_length=30)),
                ('team_number', models.IntegerField()),
            ],
        ),
        migrations.CreateModel(
            name='Event',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('event_name', models.CharField(max_length=30)),
                ('start_date', models.DateField()),
                ('end_date', models.DateField()),
                ('game', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='scouting.game')),
            ],
        ),
        migrations.CreateModel(
            name='Match',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('match_number', models.IntegerField()),
                ('event', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='+', to='scouting.event')),
                ('auton_fields', models.ManyToManyField(related_name='+', to='scouting.matchfield')),
                ('endgame_fields', models.ManyToManyField(related_name='+', to='scouting.matchfield')),
                ('post_match_fields', models.ManyToManyField(related_name='+', to='scouting.matchfield')),
                ('pre_match_fields', models.ManyToManyField(related_name='+', to='scouting.matchfield')),
                ('teleop_fields', models.ManyToManyField(related_name='+', to='scouting.matchfield')),
                ('team_blue_1', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='+', to='scouting.team')),
                ('team_blue_2', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='+', to='scouting.team')),
                ('team_blue_3', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='+', to='scouting.team')),
                ('team_red_1', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='+', to='scouting.team')),
                ('team_red_2', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='+', to='scouting.team')),
                ('team_red_3', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='+', to='scouting.team')),
            ],
        ),
    ]