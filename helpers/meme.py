import re
import discord
from constants import MEDIA_EXTS, SOCIAL_DOMAINS

URL_RE = re.compile(r"https?://[^\s<>()]+")

def is_meme_message(message: discord.Message) -> bool:
    for a in message.attachments:
        ct = (a.content_type or "").lower()
        fn = (a.filename or "").lower()

        if ct.startswith("image/") or ct.startswith("video/"):
            return True

        if any(fn.endswith(ext) for ext in MEDIA_EXTS):
            return True

    if message.embeds:
        return True

    content = (message.content or "").lower()
    urls = URL_RE.findall(content)
    for url in urls:
        if any(dom in url for dom in SOCIAL_DOMAINS):
            return True
        if any(url.endswith(ext) for ext in MEDIA_EXTS):
            return True

    return False
