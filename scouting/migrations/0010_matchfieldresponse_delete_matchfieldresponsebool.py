# Generated by Django 5.0.2 on 2024-02-16 01:07

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('scouting', '0009_rename_event_match_event_id'),
    ]

    operations = [
        migrations.CreateModel(
            name='MatchFieldResponse',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('field_value_bool', models.BooleanField(default=False)),
                ('field_value_integer', models.IntegerField(default=None)),
                ('match_field', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='scouting.matchfield')),
            ],
        ),
        migrations.DeleteModel(
            name='MatchFieldResponseBool',
        ),
    ]
