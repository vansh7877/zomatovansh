"""Main application module for AI Call Backend with LiveKit and Plivo integration."""

import os
import json
import random
from typing import Optional
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from livekit import api

load_dotenv()

app = FastAPI(
    title="AI Call Backend",
    description="Backend API for AI Call application with LiveKit and Plivo",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("ALLOWED_ORIGINS", "*"),
    allow_credentials=True,
    allow_methods=os.getenv("ALLOWED_METHODS", "*"),
    allow_headers=os.getenv("ALLOWED_HEADERS", "*"),
)


# Pydantic models for request/response
class OutboundCallRequest(BaseModel):
    """Request model for initiating an outbound call."""
    
    phone_number: str = Field(
        ...,
        description="Phone number to call in E.164 format (e.g., +15105550123)",
        example="+15105550123"
    )
    metadata: Optional[dict] = Field(
        default=None,
        description="Additional metadata to pass to the agent"
    )


class OutboundCallResponse(BaseModel):
    """Response model for outbound call initiation."""
    
    status: str
    room_name: str
    phone_number: str
    message: str


class CallStatusResponse(BaseModel):
    """Response model for call status."""
    
    room_name: str
    participants: list
    status: str


@app.get("/")
async def root() -> dict[str, str]:
    """Root endpoint."""
    return {
        "message": "Welcome to AI Call Backend API",
        "description": "Voice AI agent for outbound calling with LiveKit and Plivo"
    }


@app.get("/health")
async def health_check() -> dict[str, str]:
    """Health check endpoint."""
    return {"status": "healthy"}


@app.get("/api/v1/info")
async def info() -> dict[str, str]:
    """API information endpoint."""
    return {
        "name": "AI Call Backend",
        "version": "0.1.0",
        "status": "running",
        "features": [
            "Outbound calling with Plivo",
            "LiveKit voice agents",
            "Real-time speech recognition",
            "AI-powered conversations"
        ]
    }


@app.post("/api/v1/calls/outbound", response_model=OutboundCallResponse)
async def initiate_outbound_call(call_request: OutboundCallRequest):
    """
    Initiate an outbound call to a specified phone number.
    
    This endpoint creates a LiveKit room and dispatches an agent to make
    an outbound call via Plivo SIP trunk.
    
    Args:
        call_request: Request containing phone number and optional metadata
        
    Returns:
        OutboundCallResponse with call details
        
    Raises:
        HTTPException: If required environment variables are missing or call fails
    """
    # Validate required environment variables
    livekit_api_key = os.getenv("LIVEKIT_API_KEY")
    livekit_api_secret = os.getenv("LIVEKIT_API_SECRET")
    livekit_url = os.getenv("LIVEKIT_URL")
    
    if not all([livekit_api_key, livekit_api_secret, livekit_url]):
        raise HTTPException(
            status_code=500,
            detail="LiveKit credentials not configured. Please set LIVEKIT_API_KEY, "
                   "LIVEKIT_API_SECRET, and LIVEKIT_URL environment variables."
        )
    
    try:
        # Initialize LiveKit API client
        lkapi = api.LiveKitAPI(
            url=livekit_url,
            api_key=livekit_api_key,
            api_secret=livekit_api_secret
        )
        
        # Generate unique room name for this call
        room_name = f"outbound-call-{''.join(str(random.randint(0, 9)) for _ in range(10))}"
        
        # Prepare metadata for the agent
        agent_metadata = {
            "phone_number": call_request.phone_number,
            **(call_request.metadata or {})
        }
        
        # Dispatch agent to make the outbound call
        await lkapi.agent_dispatch.create_dispatch(
            api.CreateAgentDispatchRequest(
                agent_name="outbound-call-agent",
                room=room_name,
                metadata=json.dumps(agent_metadata)
            )
        )
        
        await lkapi.aclose()
        
        return OutboundCallResponse(
            status="success",
            room_name=room_name,
            phone_number=call_request.phone_number,
            message=f"Outbound call initiated to {call_request.phone_number}"
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to initiate outbound call: {str(e)}"
        )


@app.get("/api/v1/calls/{room_name}/status", response_model=CallStatusResponse)
async def get_call_status(room_name: str):
    """
    Get the status of an ongoing call.
    
    Args:
        room_name: The LiveKit room name for the call
        
    Returns:
        CallStatusResponse with call status and participant info
        
    Raises:
        HTTPException: If room not found or API call fails
    """
    livekit_api_key = os.getenv("LIVEKIT_API_KEY")
    livekit_api_secret = os.getenv("LIVEKIT_API_SECRET")
    livekit_url = os.getenv("LIVEKIT_URL")
    
    if not all([livekit_api_key, livekit_api_secret, livekit_url]):
        raise HTTPException(
            status_code=500,
            detail="LiveKit credentials not configured"
        )
    
    try:
        lkapi = api.LiveKitAPI(
            url=livekit_url,
            api_key=livekit_api_key,
            api_secret=livekit_api_secret
        )
        
        # List participants in the room
        participants = await lkapi.room.list_participants(
            api.ListParticipantsRequest(room=room_name)
        )
        
        await lkapi.aclose()
        
        participant_list = [
            {
                "identity": p.identity,
                "name": p.name,
                "state": p.state.name if hasattr(p.state, 'name') else str(p.state)
            }
            for p in participants
        ]
        
        return CallStatusResponse(
            room_name=room_name,
            participants=participant_list,
            status="active" if participant_list else "ended"
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=404,
            detail=f"Room not found or error retrieving status: {str(e)}"
        )


@app.post("/api/v1/calls/{room_name}/end")
async def end_call(room_name: str):
    """
    End an active call by deleting the room.
    
    Args:
        room_name: The LiveKit room name for the call
        
    Returns:
        Success message
        
    Raises:
        HTTPException: If room not found or API call fails
    """
    livekit_api_key = os.getenv("LIVEKIT_API_KEY")
    livekit_api_secret = os.getenv("LIVEKIT_API_SECRET")
    livekit_url = os.getenv("LIVEKIT_URL")
    
    if not all([livekit_api_key, livekit_api_secret, livekit_url]):
        raise HTTPException(
            status_code=500,
            detail="LiveKit credentials not configured"
        )
    
    try:
        lkapi = api.LiveKitAPI(
            url=livekit_url,
            api_key=livekit_api_key,
            api_secret=livekit_api_secret
        )
        
        await lkapi.room.delete_room(
            api.DeleteRoomRequest(room=room_name)
        )
        
        await lkapi.aclose()
        
        return {
            "status": "success",
            "message": f"Call in room {room_name} has been ended",
            "room_name": room_name
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to end call: {str(e)}"
        )

