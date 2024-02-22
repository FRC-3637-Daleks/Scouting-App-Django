from django import forms
from django.forms import modelformset_factory

from .models import *


# class StandsScoutingForm(forms.ModelForm):
#     class Meta:
#         model

class PitScoutDataForm(forms.ModelForm):
    class Meta:
        model = PitScoutData
        # fields = ['description', 'has_crisp_boombers']
        exclude = ['assigned_scout', 'team', 'event']


class MatchDataForm2024(forms.ModelForm):
    class Meta:
        model = MatchData2024
        exclude = ['team', 'match']


class MatchDataForm(forms.ModelForm):
    # id = forms.IntegerField(widget=forms.HiddenInput(), required=False)
    id = forms.IntegerField()

    class Meta:
        model = MatchData
        fields = ['id', 'match_field', 'response_bool', 'response_int']

    # def __init__(self, *args, **kwargs):
    #     team = kwargs.pop('team')
    #     event = kwargs.pop('event')
    #     match = kwargs.pop('match')
    #     match_fields = kwargs.pop('match_fields')
    #     match_fields = MatchField.objects.filter(id__in=[mf.id for mf in match_fields])
    #     super().__init__(*args, **kwargs)
    #     self.fields['match_field'].queryset = match_fields
def __init__(self, *args, **kwargs):
    team = kwargs.pop('team', None)
    event = kwargs.pop('event', None)
    match = kwargs.pop('match', None)
    match_fields = kwargs.pop('match_fields', None)
    match_fields = MatchField.objects.filter(id__in=[mf.id for mf in match_fields])
    super().__init__(*args, **kwargs)
    self.fields['match_field'].queryset = match_fields

    # Get the match_field instance
    match_field = self.instance.match_field

    # Check the field type
    if match_field.type == MatchField.FieldTypes.BOOL:
        # If it's a BOOL, use a RadioSelect widget for response_bool
        self.fields['response_bool'].widget = forms.RadioSelect(choices=[(True, 'Yes'), (False, 'No')])
        # And remove the response_int field
        del self.fields['response_int']
    elif match_field.type == MatchField.FieldTypes.INTEGER:
        # If it's an INTEGER, use a NumberInput widget for response_int
        self.fields['response_int'].widget = forms.NumberInput()
        # And remove the response_bool field
        del self.fields['response_bool']


MatchDataFormSet = modelformset_factory(MatchData, form=MatchDataForm, extra=0, can_delete=False, can_order=False)



