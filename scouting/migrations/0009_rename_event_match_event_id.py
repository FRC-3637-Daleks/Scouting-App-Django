# Generated by Django 5.0.2 on 2024-02-16 00:17

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('scouting', '0008_alter_game_year'),
    ]

    operations = [
        migrations.RenameField(
            model_name='match',
            old_name='event',
            new_name='event_id',
        ),
    ]
