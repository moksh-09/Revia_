"""
REVIA Token Server — generates LiveKit participant tokens server-side.
Never exposes LIVEKIT_API_SECRET to the frontend.

Run with:
    uvicorn token_server:app --port 7880 --reload
"""
import os
import time
import logging
import datetime
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
from livekit import api
from livekit.protocol import agent

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("token_server")

app = FastAPI(title="REVIA Token Server", version="1.0.0")

# Allow frontend to request tokens
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

LIVEKIT_URL        = os.getenv("LIVEKIT_URL", "")
LIVEKIT_API_KEY    = os.getenv("LIVEKIT_API_KEY", "")
LIVEKIT_API_SECRET = os.getenv("LIVEKIT_API_SECRET", "")
DEFAULT_ROOM       = os.getenv("LIVEKIT_DEFAULT_ROOM", "revia-room")


@app.get("/health")
def health():
    return {
        "status": "ok",
        "configured": bool(LIVEKIT_API_KEY and LIVEKIT_API_SECRET and LIVEKIT_URL),
        "livekit_url": LIVEKIT_URL,
    }


async def ensure_active_agent(lk: api.LiveKitAPI, room: str) -> None:
    """
    Ensure exactly one active revia-stt agent is running in the room.
    Kicks ghost/dead agent participants, purges stale/failed dispatches,
    and creates a new agent dispatch if no active agent job exists.
    """
    try:
        now_ns = time.time_ns()

        # 1. Fetch current participants in room
        try:
            participants_res = await lk.room.list_participants(api.ListParticipantsRequest(room=room))
            room_participants = {p.identity: p for p in participants_res.participants}
        except Exception:
            room_participants = {}

        # 2. Fetch current dispatches for this room
        try:
            dispatches = await lk.agent_dispatch.list_dispatch(room)
        except Exception:
            dispatches = []

        active_jobs = []
        active_job_identities = set()
        stale_dispatch_ids = []

        for d in dispatches:
            has_active_job = False
            created_at = getattr(d.state, "created_at", None) or getattr(d, "created_at", None) or 0
            age_s = (now_ns - created_at) / 1e9 if created_at else 999

            for j in d.state.jobs:
                # A job is genuinely active if:
                # - status is JS_PENDING (worker spinning up)
                # - OR status is JS_RUNNING and its agent participant is actually in the room
                if j.state.status == agent.JobStatus.JS_PENDING:
                    has_active_job = True
                    active_jobs.append(j)
                    if j.state.participant_identity:
                        active_job_identities.add(j.state.participant_identity)
                elif j.state.status == agent.JobStatus.JS_RUNNING:
                    agent_identity = j.state.participant_identity
                    if agent_identity and agent_identity in room_participants:
                        has_active_job = True
                        active_jobs.append(j)
                        active_job_identities.add(agent_identity)
                    else:
                        logger.warning("Job %s listed as running but %s is not in room %s", j.id, agent_identity, room)

            # If dispatch has no jobs yet, check if it was created recently (< 15 seconds ago)
            if not d.state.jobs and age_s < 15:
                has_active_job = True

            if not has_active_job:
                stale_dispatch_ids.append(d.id)

        # 3. Clean up stale dispatches
        for disp_id in stale_dispatch_ids:
            try:
                await lk.agent_dispatch.delete_dispatch(disp_id, room)
            except Exception:
                pass

        # 4. Check participants in room — kick any ghost agent participants
        for p_id, p in room_participants.items():
            if p.kind == api.ParticipantInfo.Kind.AGENT or p_id.startswith("agent-"):
                if p_id not in active_job_identities:
                    logger.warning("Evicting ghost agent participant %s from room %s", p_id, room)
                    try:
                        await lk.room.remove_participant(
                            api.RoomParticipantIdentity(room=room, identity=p_id)
                        )
                    except Exception:
                        pass

        # 5. If no genuinely active agent job is in the room, dispatch one!
        if not active_jobs:
            logger.info("No active agent job in %s; dispatching revia-stt...", room)
            req = api.CreateAgentDispatchRequest(agent_name="revia-stt", room=room)
            await lk.agent_dispatch.create_dispatch(req)
        else:
            logger.info("Room %s already has active agent job(s): %s", room, [j.id for j in active_jobs])

    except Exception as exc:
        logger.warning("ensure_active_agent note: %s", exc)



@app.get("/token")
async def get_token(
    room: str = Query(default=DEFAULT_ROOM),
    identity: str = Query(..., description="Unique participant identity"),
    name: str = Query(default=None, description="Optional display name"),
):
    """
    Generate a short-lived token for joining the LiveKit room.
    """
    if not LIVEKIT_API_KEY or not LIVEKIT_API_SECRET:
        raise HTTPException(
            status_code=500,
            detail="LiveKit credentials (LIVEKIT_API_KEY, LIVEKIT_API_SECRET) not configured in backend .env",
        )

    display_name = name or identity

    # Proactively ensure exactly one revia-stt agent is active in this room
    try:
        async with api.LiveKitAPI() as lk:
            await ensure_active_agent(lk, room)
    except Exception as exc:
        logger.info("Agent dispatch note: %s", exc)

    try:
        token = (
            api.AccessToken(LIVEKIT_API_KEY, LIVEKIT_API_SECRET)
            .with_identity(identity)
            .with_name(display_name)
            .with_ttl(datetime.timedelta(hours=6))
            .with_grants(
                api.VideoGrants(
                    room_join=True,
                    room=room,
                    can_publish=True,
                    can_subscribe=True,
                    can_publish_data=True,
                )
            )
            .to_jwt()
        )

        return {
            "token": token,
            "url": LIVEKIT_URL,
            "room": room,
            "identity": identity,
        }
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("token_server:app", host="0.0.0.0", port=7880, reload=True)
