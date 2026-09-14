from os import getenv
from dotenv import load_dotenv

load_dotenv()

# This is the new variable that broadcast.py was looking for
MONGO_DB_URI = getenv("MONGO_URL", "Apna Mongo Db Dalo")

class Config:
    def __init__(self):
        self.API_ID = int(getenv("API_ID", "17596251"))
        self.API_HASH = getenv("API_HASH", "e58343b4c0193e293e391daf97603fcd")

        self.BOT_TOKEN = getenv("BOT_TOKEN", "Apna Bot Token")
        self.MONGO_URL = getenv("MONGO_URL", "Apna Mongo Db Dalo")

        self.LOGGER_ID = int(getenv("LOGGER_ID", "Apna Log Group Id Dalo"))
        self.OWNER_ID = int(getenv("OWNER_ID", "Owner I'd dalo"))
        
        self.SESSION1 = getenv("SESSION", "BQHnBvIAiF5aVsUYZ5COCaLrPmPU7yg36Ba3Ue5p5YJyVpA1uPI4wQw2g5Cr-rPeA20FI4MkLP74nR55K3V1G5r4Ho3tXjlmSI3e8m7ltrjZ5-LcpahdEZXvdakq6Kxm-rGa60FZhPpdjRy6yGhxW8jLt8RgeYq7ZwcyT9vR0Y6I3w6NbInrFE1-PJkGnJuGexUfhFpnHrir9NOkYyx19vBKBhPX3ugm82yJVXnBMNxPFhxaRysTE8Z1ayx2PAdlb4sIxd46VpCvYmnw3xjeN1y2qQ9Df1Jn5q-STBYygzH0dbpWv8UqucfXrBWaXx14ZO1Yli966rgpXT1P__jr5u4wsgPesgAAAAH6uplCAA")
        self.SESSION2 = getenv("SESSION2", None)
        self.SESSION3 = getenv("SESSION3", None)

        self.SUPPORT_CHANNEL = getenv("SUPPORT_CHANNEL", "https://t.me/ArchonNetwork")
        self.SUPPORT_CHAT = getenv("SUPPORT_CHAT", "https://t.me/ArchonCare")
        self.OWNER_USERNAME = getenv("OWNER_USERNAME", "https://t.me/TeamArchon?direct")

        self.AUTO_END: bool = getenv("AUTO_END", False)
        self.AUTO_LEAVE: bool = getenv("AUTO_LEAVE", False)
        self.VIDEO_PLAY: bool = getenv("VIDEO_PLAY", True)

        self.QUEUE_LIMIT = int(getenv("QUEUE_LIMIT", "200"))
        self.DURATION_LIMIT = int(getenv("DURATION_LIMIT", "17000"))
        self.PLAYLIST_LIMIT = int(getenv("PLAYLIST_LIMIT", "200"))
        self.YOUTUBE_API_KEY = getenv("YOUTUBE_API_KEY", "INFLEX86759628D")
        self.DEFAULT_THUMB = getenv("DEFAULT_THUMB", "https://n.uguu.se/EBVPCnuG.jpg")
        
        # --- PING VIDEO LINK ---
        self.PING_IMG = getenv("PING_IMG", "https://graph.org/file/286aa2427c36ca129f609-b2da780c99e73d27a7.mp4")
        
        # --- START VIDEO LINK ---
        self.START_IMG = getenv("START_IMG", "https://graph.org/file/c83bb8064b95ee51e515c-6c4626e964f37fc102.jpg")
        self.START_VIDEO = getenv("START_VIDEO", "https://graph.org/file/3a79f5b7dfb1e423b49d3-eacd9bc472c36d5be6.mp4")

    def check(self):
        missing = [
            var
            for var in ["API_ID", "API_HASH", "BOT_TOKEN", "MONGO_URL", "LOGGER_ID", "OWNER_ID", "SESSION1"]
            if not getattr(self, var)
        ]
        if missing:
            raise SystemExit(f"Missing required environment variables: {', '.join(missing)}")
