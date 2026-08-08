"""
Chat API Routes — WebSocket-based interactive Q&A.
"""

import asyncio
import json
import logging
from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect, status
from langchain_core.messages import AIMessage, HumanMessage

from app.agents.graph import get_chat_graph
from app.api.auth import get_current_user, get_current_websocket_user
from app.security.rate_limit import RateLimitRule, check_rate_limit, rate_limit, websocket_identity
from app.services.user_data import clear_user_chat, get_user_chat, upsert_user_chat, list_user_chats, delete_user_chat

router = APIRouter(tags=["Chat"])
logger = logging.getLogger(__name__)

CHAT_HTTP_RATE_LIMIT = rate_limit("chat:http", max_requests=20, window_seconds=60)
CHAT_WS_MESSAGE_LIMIT = RateLimitRule("chat:websocket", max_requests=30, window_seconds=60)
CHAT_GRAPH_TIMEOUT_SECONDS = 40


def _extract_text_content(content) -> str:
    if isinstance(content, str):
        return content
    elif isinstance(content, list):
        return "".join([c.get("text", "") for c in content if isinstance(c, dict) and c.get("type") == "text"])
    return str(content)


def _stored_messages_to_langchain(messages: list[dict]) -> list:
    converted = []
    for message in messages:
        role = message.get("role")
        content = message.get("content", "")
        content = _extract_text_content(content)
        if not content:
            continue
        if role == "user":
            converted.append(HumanMessage(content=content))
        elif role == "ai":
            converted.append(AIMessage(content=content))
    return converted


def _langchain_messages_to_stored(messages: list) -> list[dict]:
    stored = []
    for message in messages:
        msg_type = getattr(message, "type", None)
        if msg_type == "human":
            stored.append({"role": "user", "content": _extract_text_content(message.content)})
        elif msg_type == "ai":
            stored.append({"role": "ai", "content": _extract_text_content(message.content)})
    return stored


@router.websocket("/api/chat")
async def chat_websocket(websocket: WebSocket):
    """
    WebSocket endpoint for interactive chat with the insurance AI assistant.

    Protocol:
    - Client sends: {"message": "user's question", "policy_profile": {...} (optional)}
    - Server responds: {"response": "AI answer", "error": null}
    """
    try:
        user = get_current_websocket_user(websocket)
    except Exception:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    await websocket.accept()
    ws_identity = websocket_identity(user)
    chat = get_user_chat(user["id"])
    logger.info("Chat WebSocket: Authenticated connection opened for user %s", user.get("id"))

    # Persistent state across the conversation
    conversation_state = {
        "messages": _stored_messages_to_langchain(chat.get("messages", []) if chat else []),
        "raw_policy_text": "",
        "raw_claim_text": "",
        "policy_profile": (chat or {}).get("policy_profile_json"),
        "claim_case": None,
        "allowed_amount": None,
        "cost_breakdown": (chat or {}).get("cost_breakdown_json"),
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
                check_rate_limit(ws_identity, CHAT_WS_MESSAGE_LIMIT)
            except Exception as exc:
                detail = getattr(exc, "detail", "Rate limit exceeded. Please wait and try again.")
                await websocket.send_json({"response": None, "error": detail})
                continue

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
            result = await asyncio.wait_for(graph.ainvoke(conversation_state), timeout=CHAT_GRAPH_TIMEOUT_SECONDS)

            # Extract the new AI messages and append them to our persistent history.
            # The graph uses add_messages, so result["messages"] contains ALL messages
            # (old + new). We need to find the new ones and add them to our state.
            result_messages = result.get("messages", [])
            # The new AI response is the last message(s) added by the graph
            new_ai_messages = [
                m for m in result_messages 
                if hasattr(m, 'type') and m.type == "ai" 
                and m not in conversation_state["messages"]
            ]
            
            if new_ai_messages:
                conversation_state["messages"].extend(new_ai_messages)
                response_text = _extract_text_content(new_ai_messages[-1].content)
            else:
                # Fallback: get the last AI message from the full result
                all_ai = [m for m in result_messages if hasattr(m, 'type') and m.type == "ai"]
                response_text = _extract_text_content(all_ai[-1].content) if all_ai else "I couldn't generate a response."
                # Sync state with full result to avoid drift
                conversation_state["messages"] = result_messages

            stored_after = _langchain_messages_to_stored(conversation_state["messages"])
            upsert_user_chat(
                user["id"],
                stored_after,
                policy_profile=conversation_state.get("policy_profile"),
                cost_breakdown=conversation_state.get("cost_breakdown"),
            )

            await websocket.send_json({
                "response": response_text,
                "error": None,
                "messages": stored_after,
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


@router.get("/api/chat/sessions", tags=["Chat"])
async def get_all_chat_sessions(user: dict = Depends(get_current_user)):
    return list_user_chats(user["id"])


@router.get("/api/chat/session", tags=["Chat"])
async def get_chat_session(chat_id: str | None = None, user: dict = Depends(get_current_user)):
    if not chat_id:
        return {"messages": [], "policy_profile": None, "cost_breakdown": None}
    
    chat = get_user_chat(user["id"], chat_id)
    if not chat:
        return {"messages": [], "policy_profile": None, "cost_breakdown": None}
    return {
        "id": chat.get("id"),
        "title": chat.get("title"),
        "messages": chat.get("messages") or [],
        "policy_profile": chat.get("policy_profile_json"),
        "cost_breakdown": chat.get("cost_breakdown_json"),
    }


@router.delete("/api/chat/session/{chat_id}", tags=["Chat"])
async def delete_chat_session(chat_id: str, user: dict = Depends(get_current_user)):
    success = delete_user_chat(user["id"], chat_id)
    return {"success": success}


@router.post("/api/chat/message", tags=["Chat"])
async def chat_message(request: dict, user: dict = Depends(get_current_user), _: None = Depends(CHAT_HTTP_RATE_LIMIT)):
    """
    HTTP POST alternative for chat (for clients that don't support WebSocket).

    Body: {"message": "...", "history": [...], "policy_profile": {...}}
    """
    chat_id = request.get("chat_id")
    user_message = request.get("message", "")
    if not user_message.strip():
        return {"response": "Please type a question.", "error": None}

    if chat_id:
        chat = get_user_chat(user["id"], chat_id)
    else:
        chat = None

    stored_messages = chat.get("messages", []) if chat else []
    messages = _stored_messages_to_langchain(stored_messages)
    messages.append(HumanMessage(content=user_message))

    policy_profile = request.get("policy_profile") or (chat or {}).get("policy_profile_json")
    cost_breakdown = request.get("cost_breakdown") or (chat or {}).get("cost_breakdown_json")

    state = {
        "messages": messages,
        "raw_policy_text": "",
        "raw_claim_text": "",
        "policy_profile": policy_profile,
        "claim_case": request.get("claim_case"),
        "allowed_amount": request.get("allowed_amount"),
        "cost_breakdown": cost_breakdown,
        "appeal_output": None,
        "current_phase": "chat",
        "route_decision": "",
        "errors": [],
        "explanations": {},
    }

    try:
        graph = get_chat_graph()
        result = await asyncio.wait_for(graph.ainvoke(state), timeout=CHAT_GRAPH_TIMEOUT_SECONDS)

        ai_messages = [m for m in result.get("messages", []) if hasattr(m, 'type') and m.type == "ai"]
        response_text = _extract_text_content(ai_messages[-1].content) if ai_messages else "I couldn't generate a response."
        stored_after = _langchain_messages_to_stored(result.get("messages", []))
        
        title = None
        if not chat_id and len(stored_after) <= 2:
            title = user_message[:30] + ("..." if len(user_message) > 30 else "")

        new_chat = upsert_user_chat(
            user["id"], 
            stored_after, 
            policy_profile=policy_profile, 
            cost_breakdown=cost_breakdown,
            chat_id=chat_id,
            title=title
        )
        
        res_chat_id = new_chat["id"] if new_chat else chat_id

        return {"response": response_text, "error": None, "messages": stored_after, "chat_id": res_chat_id}

    except Exception as e:
        logger.error(f"Chat HTTP error: {e}", exc_info=True)
        return {"response": None, "error": str(e)}
