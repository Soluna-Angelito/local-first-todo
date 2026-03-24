"""WebSocket API for real-time updates in Local-First To-Do application."""

import asyncio
import json
import logging
from typing import Set, Dict, Any

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from fastapi.websockets import WebSocketState

logger = logging.getLogger(__name__)

router = APIRouter()

# WebSocket connection management
class ConnectionManager:
    """Manages WebSocket connections and broadcasting."""
    
    def __init__(self):
        self.active_connections: Set[WebSocket] = set()
        self.connection_metadata: Dict[WebSocket, Dict[str, Any]] = {}
    
    async def connect(self, websocket: WebSocket) -> None:
        """Accept a new WebSocket connection."""
        await websocket.accept()
        self.active_connections.add(websocket)
        self.connection_metadata[websocket] = {
            "connected_at": asyncio.get_event_loop().time(),
            "last_ping": asyncio.get_event_loop().time(),
        }
        logger.info(f"WebSocket connected. Total connections: {len(self.active_connections)}")
    
    def disconnect(self, websocket: WebSocket) -> None:
        """Remove a WebSocket connection."""
        self.active_connections.discard(websocket)
        self.connection_metadata.pop(websocket, None)
        logger.info(f"WebSocket disconnected. Total connections: {len(self.active_connections)}")
    
    async def send_personal_message(self, message: Dict[str, Any], websocket: WebSocket) -> None:
        """Send a message to a specific WebSocket connection."""
        if websocket in self.active_connections:
            try:
                await websocket.send_text(json.dumps(message))
            except Exception as e:
                logger.error(f"Error sending personal message: {e}")
                self.disconnect(websocket)
    
    async def broadcast(self, message: Dict[str, Any]) -> None:
        """Broadcast a message to all connected WebSocket clients."""
        if not self.active_connections:
            return
        
        disconnected = set()
        message_json = json.dumps(message)
        
        for connection in self.active_connections:
            try:
                if connection.client_state == WebSocketState.CONNECTED:
                    await connection.send_text(message_json)
                else:
                    disconnected.add(connection)
            except Exception as e:
                logger.error(f"Error broadcasting to connection: {e}")
                disconnected.add(connection)
        
        # Clean up disconnected connections
        for connection in disconnected:
            self.disconnect(connection)
    
    async def broadcast_task_update(self, event_type: str, task_data: Dict[str, Any]) -> None:
        """Broadcast a task-related update to all clients."""
        message = {
            "type": "task_update",
            "event": event_type,  # created, updated, deleted, restored, moved
            "data": task_data,
            "timestamp": asyncio.get_event_loop().time()
        }
        await self.broadcast(message)
    
    async def send_ping(self, websocket: WebSocket) -> None:
        """Send a ping message to a specific connection."""
        ping_message = {
            "type": "ping",
            "timestamp": asyncio.get_event_loop().time()
        }
        await self.send_personal_message(ping_message, websocket)
        
        if websocket in self.connection_metadata:
            self.connection_metadata[websocket]["last_ping"] = asyncio.get_event_loop().time()
    
    async def handle_pong(self, websocket: WebSocket, pong_data: Dict[str, Any]) -> None:
        """Handle a pong response from a client."""
        if websocket in self.connection_metadata:
            self.connection_metadata[websocket]["last_pong"] = asyncio.get_event_loop().time()
            
        # Send acknowledgment
        ack_message = {
            "type": "pong_ack",
            "timestamp": asyncio.get_event_loop().time()
        }
        await self.send_personal_message(ack_message, websocket)
    
    async def handle_reset_needed(self, websocket: WebSocket, since_revision: int = 0) -> None:
        """Send a reset_needed message to a client that needs to resynchronize."""
        reset_message = {
            "type": "reset_needed",
            "reason": "Client state is too stale",
            "since_revision": since_revision,
            "timestamp": asyncio.get_event_loop().time()
        }
        await self.send_personal_message(reset_message, websocket)


# Global connection manager
manager = ConnectionManager()


@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """Main WebSocket endpoint for real-time communication."""
    await manager.connect(websocket)
    
    try:
        # Send initial connection confirmation
        welcome_message = {
            "type": "connected",
            "message": "WebSocket connection established",
            "timestamp": asyncio.get_event_loop().time()
        }
        await manager.send_personal_message(welcome_message, websocket)
        
        # Message handling loop
        while True:
            try:
                # Wait for messages with timeout to implement ping/pong
                data = await asyncio.wait_for(websocket.receive_text(), timeout=30.0)
                
                try:
                    message = json.loads(data)
                    await handle_websocket_message(websocket, message)
                except json.JSONDecodeError:
                    error_message = {
                        "type": "error",
                        "message": "Invalid JSON format",
                        "timestamp": asyncio.get_event_loop().time()
                    }
                    await manager.send_personal_message(error_message, websocket)
                    
            except asyncio.TimeoutError:
                # Send ping if no message received within timeout
                try:
                    await manager.send_ping(websocket)
                except Exception as e:
                    logger.error(f"Error sending ping: {e}")
                    break
                    
    except WebSocketDisconnect:
        logger.info("WebSocket disconnected normally")
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
    finally:
        manager.disconnect(websocket)


async def handle_websocket_message(websocket: WebSocket, message: Dict[str, Any]) -> None:
    """Handle incoming WebSocket messages from clients."""
    message_type = message.get("type")
    
    if message_type == "pong":
        await manager.handle_pong(websocket, message)
        
    elif message_type == "sync_request":
        # Client requesting synchronization
        since_revision = message.get("since_revision", 0)
        
        # For now, we'll send a reset_needed response
        # In Phase 7, this will be replaced with actual delta sync
        await manager.handle_reset_needed(websocket, since_revision)
        
    elif message_type == "heartbeat":
        # Client heartbeat - respond with acknowledgment
        heartbeat_ack = {
            "type": "heartbeat_ack",
            "timestamp": asyncio.get_event_loop().time()
        }
        await manager.send_personal_message(heartbeat_ack, websocket)
        
    else:
        # Unknown message type
        error_message = {
            "type": "error",
            "message": f"Unknown message type: {message_type}",
            "timestamp": asyncio.get_event_loop().time()
        }
        await manager.send_personal_message(error_message, websocket)


# Function to be used by other modules to broadcast updates
async def broadcast_task_update(event_type: str, task_data: Dict[str, Any]) -> None:
    """Broadcast a task update to all connected WebSocket clients."""
    await manager.broadcast_task_update(event_type, task_data)


# Background task for periodic connection health checks
async def websocket_health_check():
    """Background task to check WebSocket connection health."""
    while True:
        try:
            await asyncio.sleep(60)  # Check every minute
            
            current_time = asyncio.get_event_loop().time()
            stale_connections = set()
            
            for connection, metadata in manager.connection_metadata.items():
                last_activity = max(
                    metadata.get("last_ping", 0),
                    metadata.get("last_pong", 0),
                    metadata.get("connected_at", 0)
                )
                
                # Consider connection stale after 5 minutes of no activity
                if current_time - last_activity > 300:
                    stale_connections.add(connection)
            
            # Clean up stale connections
            for connection in stale_connections:
                logger.info("Cleaning up stale WebSocket connection")
                manager.disconnect(connection)
                try:
                    await connection.close()
                except Exception:
                    pass  # Connection might already be closed
                    
        except Exception as e:
            logger.error(f"Error in WebSocket health check: {e}")
            await asyncio.sleep(10)  # Shorter sleep on error 