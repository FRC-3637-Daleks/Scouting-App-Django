from django.urls import re_path
from DjangoScoutingApp import consumers

websocket_urlpatterns = [
    re_path(r'ws/priority/$', consumers.PriorityConsumer.as_asgi()),
]
