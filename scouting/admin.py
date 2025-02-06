from django.contrib import admin

from .models import *

admin.site.register(Game)
admin.site.register(Event)
admin.site.register(Team)
admin.site.register(Match)
# admin.site.register(MatchField)
admin.site.register(MatchData2025)
admin.site.register(TbaApiKey)
admin.site.register(PitScoutData)

