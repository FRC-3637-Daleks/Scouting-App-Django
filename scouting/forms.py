from django import forms
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Layout, Div, Field, ButtonHolder, Submit

from .models import *


class PitScoutDataForm(forms.ModelForm):
    class Meta:
        model = PitScoutData
        exclude = ['assigned_scout', 'team', 'event']


class MatchData2024Form(forms.ModelForm):
    class Meta:
        model = MatchData2024
        exclude = ['team', 'match']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_tag = False  # No <form> tags

        # Group fields by section
        self.field_groups = {
            'Pre-Match': ['arrived_on_field_on_time', 'start_with_note', 'dead_on_arrival', 'starting_location'],
            'Auton': ['left_community_zone', 'a_stopped', 'auton_amp_notes_scored', 'auton_speaker_notes_scored', 'auton_notes_picked_up'],
            'Teleop': ['e_stopped', 'communication_lost', 'teleop_amp_notes_scored', 'teleop_speaker_notes_scored', 'teleop_notes_missed'],
            'Endgame': ['climbed_solo', 'climbed_with_another_robot', 'scored_high_notes', 'notes_scored_in_trap'],
        }

        layout_fields = []
        for section, fields in self.field_groups.items():
            layout_fields.append(
                Div(
                    *[Field(field) for field in fields],
                )
            )
        self.helper.layout = Layout(*layout_fields, ButtonHolder(Submit('submit', 'Save', css_class='btn-primary')))
