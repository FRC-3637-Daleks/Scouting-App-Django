from django import forms
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Layout, Div, Field, ButtonHolder, Submit
from django.forms.widgets import RadioSelect, ClearableFileInput

from .models import *

from django.forms.widgets import RadioSelect

class PitScoutDataForm(forms.ModelForm):
    class Meta:
        model = PitScoutData
        fields = '__all__'
        widgets = {
            'crisp_boomers': RadioSelect(choices=((True, 'Yes'), (False, 'No'))),
            'friendly': RadioSelect(choices=((True, 'Yes'), (False, 'No'))),
            'auton_picture1': ClearableFileInput(),
            'auton_picture2': ClearableFileInput(),  # Explicit widget for image field
            'auton_picture3': ClearableFileInput(),
            'robot_picture1': ClearableFileInput(),
            'robot_picture2': ClearableFileInput(),
        }
        exclude = ['assigned_scout', 'team', 'event']

class MatchData2025Form(forms.ModelForm):
    class Meta:
        model = MatchData2025
        exclude = ['team', 'match']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_tag = False  # No <form> tags

        # Group fields by section
        self.field_groups = {
            'Match': ['defense_effectiveness', 'scoring_accuracy_or_effectiveness', 'human_player_accuracy', 'compatibility_with_alliance_members', 'other_comments']
        }

        layout_fields = []
        for section, fields in self.field_groups.items():
            layout_fields.append(
                Div(
                    *[Field(field) for field in fields],
                )
            )
        self.helper.layout = Layout(*layout_fields, ButtonHolder(Submit('submit', 'Save', css_class='btn-primary')))
