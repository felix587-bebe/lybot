import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
DB_PATH = os.getenv("DB_PATH", "musicbot.db")

# OnyxGram custom Bot API server. Pinned here (not official api.telegram.org)
# per project requirement.
ONYXGRAM_API_URL = os.getenv("ONYXGRAM_API_URL", "https://dev-angel-7553.dev")

# Render injects PORT automatically for web services; a free-tier web
# service MUST bind this port or the health check marks the deploy
# unhealthy. Default is just for local runs.
PORT = int(os.getenv("PORT", "10000"))

# Render also injects RENDER_EXTERNAL_URL automatically on web services.
# Used (if present) to self-ping and stop the free instance from
# sleeping after ~15 min of no HTTP traffic. Leave unset locally.
RENDER_EXTERNAL_URL = os.getenv("RENDER_EXTERNAL_URL")
