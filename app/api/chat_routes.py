"""
Chat API Routes — WebSocket-based interactive Q&A.
"""

import json
import logging
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from langchain_core.messages import HumanMessage

from app.agents.graph import get_chat_graph

router = APIRouter(tags=["Chat"])
logger = logging.getLogger(__name__)


@router.websocket("/api/chat")
async def chat_websocket(websocket: WebSocket):
    """
    WebSocket endpoint for interactive chat with the insurance AI assistant.

    Protocol:
    - Client sends: {"message": "user's question", "policy_profile": {...} (optional)}
    - Server responds: {"response": "AI answer", "error": null}
    """
    await websocket.accept()
    logger.info("Chat WebSocket: Connection opened")

    # Persistent state across the conversation
    conversation_state = {
        "messages": [],
        "raw_policy_text": "",
        "raw_claim_text": "",
        "policy_profile": None,
        "claim_case": None,
        "cost_breakdown": None,
        "appeal_output": None,
        "current_phase": "chat",
        "route_decision": "",
        "errors": [],
        "explanations": {},
    }

    try:
        while True:
            # Receive message from client
            data = await websocket.receive_text()

            try:
                payload = json.loads(data)
                user_message = payload.get("message", "")

                # Update policy context if provided
                if payload.get("policy_profile"):
                    conversation_state["policy_profile"] = payload["policy_profile"]

                # Update cost breakdown context if provided
                if payload.get("cost_breakdown"):
                    conversation_state["cost_breakdown"] = payload["cost_breakdown"]

            except json.JSONDecodeError:
                user_message = data  # Treat raw text as the message

            if not user_message.strip():
                await websocket.send_json({"response": "Please type a question.", "error": None})
                continue

            # Add user message to conversation history
            conversation_state["messages"].append(HumanMessage(content=user_message))

            # Run the chat graph
            graph = get_chat_graph()
            result = await graph.ainvoke(conversation_state)

            # Update conversation state with new messages
            conversation_state["messages"] = result.get("messages", conversation_state["messages"])

            # Extract the latest AI response
            ai_messages = [m for m in conversation_state["messages"] if hasattr(m, 'type') and m.type == "ai"]
            response_text = ai_messages[-1].content if ai_messages else "I couldn't generate a response."

            await websocket.send_json({
                "response": response_text,
                "error": None,
            })

    except WebSocketDisconnect:
        logger.info("Chat WebSocket: Connection closed")
    except Exception as e:
        logger.error(f"Chat WebSocket error: {e}", exc_info=True)
        try:
            await websocket.send_json({
                "response": None,
                "error": f"An error occurred: {str(e)}",
            })
        except Exception:
            pass


@router.post("/api/chat/message", tags=["Chat"])
async def chat_message(request: dict):
    """
    HTTP POST alternative for chat (for clients that don't support WebSocket).

    Body: {"message": "...", "history": [...], "policy_profile": {...}}
    """
    user_message = request.get("message", "")
    if not user_message.strip():
        return {"response": "Please type a question.", "error": None}

    # Build state from request
    history = request.get("history", [])
    messages = [HumanMessage(content=msg) for msg in history]
    messages.append(HumanMessage(content=user_message))

    state = {
        "messages": messages,
        "raw_policy_text": "",
        "raw_claim_text": "",
        "policy_profile": request.get("policy_profile"),
        "claim_case": request.get("claim_case"),
        "cost_breakdown": request.get("cost_breakdown"),
        "appeal_output": None,
        "current_phase": "chat",
        "route_decision": "",
        "errors": [],
        "explanations": {},
    }

    try:
        graph = get_chat_graph()
        result = await graph.ainvoke(state)

        ai_messages = [m for m in result.get("messages", []) if hasattr(m, 'type') and m.type == "ai"]
        response_text = ai_messages[-1].content if ai_messages else "I couldn't generate a response."

        return {"response": response_text, "error": None}

    except Exception as e:
        logger.error(f"Chat HTTP error: {e}", exc_info=True)
        return {"response": None, "error": str(e)}
