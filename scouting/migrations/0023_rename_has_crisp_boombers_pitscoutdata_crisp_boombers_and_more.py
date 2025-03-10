# Generated by Django 5.0.2 on 2024-02-22 01:06

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('scouting', '0022_pitscoutdata_can_climb_and_more'),
    ]

    operations = [
        migrations.RenameField(
            model_name='pitscoutdata',
            old_name='has_crisp_boombers',
            new_name='Crisp Boombers',
        ),
        migrations.AddField(
            model_name='matchdata2024',
            name='climbed_solo',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='matchdata2024',
            name='climbed_with_another_robot',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='matchdata2024',
            name='defense_scale',
            field=models.IntegerField(default=0),
        ),
        migrations.AddField(
            model_name='matchdata2024',
            name='notes_dropped',
            field=models.IntegerField(default=0),
        ),
        migrations.AddField(
            model_name='matchdata2024',
            name='notes_picked_up_from_floor',
            field=models.IntegerField(default=0),
        ),
        migrations.AddField(
            model_name='matchdata2024',
            name='notes_picked_up_from_player_station',
            field=models.IntegerField(default=0),
        ),
        migrations.AddField(
            model_name='matchdata2024',
            name='notes_scored_in_trap',
            field=models.IntegerField(default=0),
        ),
        migrations.AddField(
            model_name='matchdata2024',
            name='scored_high_notes',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='matchdata2024',
            name='shoots_from_free_space_to_speaker',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='matchdata2024',
            name='shoots_from_podium_to_speaker',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='matchdata2024',
            name='shoots_from_subwoofer_to_speaker',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='matchdata2024',
            name='speaker_notes_missed',
            field=models.IntegerField(default=0),
        ),
    ]
