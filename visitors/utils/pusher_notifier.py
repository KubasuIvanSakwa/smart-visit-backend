import pusher
from django.conf import settings

pusher_client = pusher.Pusher(
    app_id=settings.PUSHER_APP_ID,
    key=settings.PUSHER_KEY,
    secret=settings.PUSHER_SECRET,
    cluster=settings.PUSHER_CLUSTER,
    ssl=settings.PUSHER_SSL,
)

def trigger_host_notification(channel, event, data):
    """
    Trigger a Pusher event.
    """
    pusher_client.trigger(channel, event, data)
