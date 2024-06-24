

from textual.events import Event
import logging

from inventree_tui.settings import settings

class NullSound():
    def play(self):
        pass

if settings.sound_enabled:
    if settings.tts_enabled:
        from .generation import tts as _tts
    from .chimes import success as success_chime, failure as failure_chime
    #import .generation as generation
    # Generate the sounds
    success = success_chime()
    failure = failure_chime()
else:
    success = NullSound()
    failure = NullSound()

def tts(text):
    if not settings.sound_enabled:
        return None
    if not (settings.tts_enabled):
        return NullSound()

    return _tts(text.lower().strip())

def play_sound(sound_name: str):
    if not settings.sound_enabled:
        return False
    if sound_name == "success":
        success.play()
    elif sound_name == "failure":
        failure.play()

class Sound(Event):
    def __init__(self, sender, name: str = None, fn = None):
        super().__init__()
        self.sender = sender
        self.name = name
        self.fn = fn
