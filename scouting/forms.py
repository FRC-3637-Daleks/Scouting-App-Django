from django import forms
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Layout, Div, Field, ButtonHolder, Submit
from django.forms.widgets import RadioSelect, ClearableFileInput

from .models import *

from django.forms.widgets import RadioSelect

class PitScoutDataForm(forms.ModelForm):
    IMAGE_FIELDS = [
        'auton_picture_1',
        'auton_picture_2',
        'auton_picture_3',
        'robot_picture_1',
        'robot_picture_2',
    ]

    class Meta:
        model = PitScoutData
        fields = '__all__'
        widgets = {
            'friendly_or_cool': RadioSelect(choices=((True, 'Yes'), (False, 'No'))),
            'crisp_boompers': RadioSelect(choices=((True, 'Yes'), (False, 'No'))),
            'can_robot_l3_climb': RadioSelect(choices=((True, 'Yes'), (False, 'No'))),
            'can_robot_l1_climb': RadioSelect(choices=((True, 'Yes'), (False, 'No'))),
            'can_robot_l1_climb_in_auto': RadioSelect(choices=((True, 'Yes'), (False, 'No'))),
            'auton_picture_1': ClearableFileInput(),
            'auton_picture_2': ClearableFileInput(),
            'auton_picture_3': ClearableFileInput(),
            'robot_picture_1': ClearableFileInput(),
            'robot_picture_2': ClearableFileInput(),
        }
        labels = {
            'can_robot_l3_climb': 'Can robot L3 climb',
            'can_robot_l1_climb': 'Can robot L1 climb',
            'can_robot_l1_climb_in_auto': 'Can robot L1 climb in AUTO',
        }
        exclude = ['assigned_scout', 'team', 'event']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Hint mobile browsers to open camera; desktop still uses file picker.
        for field_name in self.IMAGE_FIELDS:
            if field_name in self.fields:
                self.fields[field_name].widget.attrs.update({
                    'accept': 'image/*',
                    'capture': 'environment',
                })

class MatchData2026Form(forms.ModelForm):
    class Meta:
        model = MatchData2026
        exclude = ['team', 'match']
        labels = {
            'defense_effectiveness': 'Defense Effectiveness (Tower/Hub Denial)',
            'scoring_accuracy_or_effectiveness': 'Fuel Scoring Accuracy / Effectiveness',
            'human_player_accuracy': 'Human Player Fuel Handling',
            'compatibility_with_alliance_members': 'Alliance Compatibility',
            'tower_climb_time': 'Tower Climb Time (seconds)',
            'other_comments': 'Other Match Notes',
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_tag = False  # No <form> tags

        # Group fields by section
        self.field_groups = {
            'Match': [
                'defense_effectiveness',
                'scoring_accuracy_or_effectiveness',
                'human_player_accuracy',
                'compatibility_with_alliance_members',
                'tower_climb_time',
                'other_comments',
            ]
        }

        layout_fields = []
        for section, fields in self.field_groups.items():
            layout_fields.append(
                Div(
                    *[Field(field) for field in fields],
                )
            )
        self.helper.layout = Layout(*layout_fields, ButtonHolder(Submit('submit', 'Save', css_class='btn-primary')))
