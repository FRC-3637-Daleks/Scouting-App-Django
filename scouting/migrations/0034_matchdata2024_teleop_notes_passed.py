# Generated by Django 5.0.2 on 2024-04-18 13:25

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('scouting', '0033_matchdata2024_comments'),
    ]

    operations = [
        migrations.AddField(
            model_name='matchdata2024',
            name='teleop_notes_passed',
            field=models.IntegerField(default=0),
        ),
    ]
