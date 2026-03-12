from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("scouting", "0053_alter_pitscoutdata_auton_picture_1_and_more"),
    ]

    operations = [
        migrations.RenameField(
            model_name="pitscoutdata",
            old_name="crisp_boomers",
            new_name="crisp_boompers",
        ),
        migrations.AddField(
            model_name="pitscoutdata",
            name="can_robot_l1_climb",
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name="pitscoutdata",
            name="can_robot_l1_climb_in_auto",
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name="pitscoutdata",
            name="can_robot_l3_climb",
            field=models.BooleanField(default=False),
        ),
    ]
