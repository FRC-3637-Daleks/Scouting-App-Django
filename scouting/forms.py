from django import forms
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Layout, Div, Field, ButtonHolder, Submit

from .models import *

from django.forms.widgets import RadioSelect

class PitScoutDataForm(forms.ModelForm):
    class Meta:
        model = PitScoutData
        fields = '__all__'
        widgets = {'crisp_boomers': RadioSelect(
            choices=((True, 'Yes'), (False, 'No'))
        ), 'friendly': RadioSelect(choices=((True, 'Yes'), (False, 'No')))}
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
            'Match': ['defense_text', 'counter_defense_text', 'human_player', 'compatibility', 'other_comments']
        }

        layout_fields = []
        for section, fields in self.field_groups.items():
            layout_fields.append(
                Div(
                    *[Field(field) for field in fields],
                )
            )
        self.helper.layout = Layout(*layout_fields, ButtonHolder(Submit('submit', 'Save', css_class='btn-primary')))
