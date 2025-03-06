import os
import django
from channels.routing import ProtocolTypeRouter, URLRouter
from channels.auth import AuthMiddlewareStack
from django.core.asgi import get_asgi_application
import scouting.routing

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'DjangoScoutingApp.settings')
django.setup()

application = ProtocolTypeRouter({
    "http": get_asgi_application(),
    "websocket": AuthMiddlewareStack(
        URLRouter(
            scouting.routing.websocket_urlpatterns
        )
    ),
})
