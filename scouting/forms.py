from django import forms
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Layout, Div, Field, ButtonHolder, Submit

from .models import *


class PitScoutDataForm(forms.ModelForm):
    class Meta:
        model = PitScoutData
        exclude = ['assigned_scout', 'team', 'event', 'id']


class MatchData2024Form(forms.ModelForm):
    class Meta:
        model = MatchData2024
        exclude = ['team', 'match', 'id']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_tag = False  # No <form> tags

        # Group fields by section
        self.field_groups = {
            'Pre-Match': ['arrived_on_field_on_time', 'start_with_note', 'dead_on_arrival', 'starting_location'],
            'Auton': ['left_community_zone', 'moved', 'a_stopped', 'amp_notes_scored', 'speaker_notes_scored', 'notes_picked_up_from_wing', 'notes_picked_up_from_center', 'time_to_centerline_note'],
            'Teleop': ['e_stopped', 'communication_lost', 'shoots_from_subwoofer_to_speaker', 'shoots_from_podium_to_speaker', 'shoots_from_free_space_to_speaker', 'amp_notes_scored', 'notes_scored_from_subwoofer', 'notes_scored_from_elesewhere', 'speaker_notes_missed', 'defense_scale', 'notes_picked_up_from_floor', 'notes_dropped', 'notes_picked_up_from_player_station'],
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
