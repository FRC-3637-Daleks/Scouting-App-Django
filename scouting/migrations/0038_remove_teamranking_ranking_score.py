# Generated by Django 5.0.2 on 2025-03-06 00:35

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('scouting', '0037_rename_compatibility_matchdata2025_compatibility_with_alliance_members_and_more'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='teamranking',
            name='ranking_score',
        ),
    ]
