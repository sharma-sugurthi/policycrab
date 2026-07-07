"""
Agent 5: Chat — Interactive Q&A agent for patient questions.

Uses RAG retrieval from the knowledge base to answer questions
about insurance, claims, appeals, and regulations. Restricted
to the US health insurance domain.
"""

import logging
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage

from app.agents.state import AgentState
from app.services.llm_router import get_llm, TaskType, generate_embedding
from app.services.supabase_client import search_knowledge_base
from app.tools.provider_search import ProviderSearchTool
from app.tools.network_status import NetworkStatusTool
from langchain_core.messages import ToolMessage

logger = logging.getLogger(__name__)

CHAT_SYSTEM_PROMPT = """You are an AI health insurance assistant specializing in the 
US healthcare system. You help patients understand their insurance policies, claims, 
denials, appeals, and rights.

DOMAIN RESTRICTION: You ONLY answer questions about US health insurance. If asked about 
anything unrelated (cooking, sports, politics, etc.), politely redirect: "I'm specialized 
in US health insurance. I can help you understand your coverage, claims, denials, or appeals."

ACCURACY RULES:
1. Use the retrieved knowledge base excerpts (provided below) as your PRIMARY source
2. If the knowledge base has relevant information, cite it directly
3. If you're unsure or the knowledge base doesn't cover the topic, say so honestly
4. NEVER fabricate regulations, deadlines, or dollar amounts
5. Always specify whether something is federal law vs. state-specific
6. When mentioning deadlines, give specific timeframes (e.g., "180 days under ERISA")

TONE: Empathetic, clear, actionable. The patient is likely stressed about a medical bill 
or denial. Be supportive while being accurate.

FORMAT: Keep responses concise (under 250 words unless the question requires detail).
Use bullet points for lists. Bold key terms.

TOOLS:
You have access to tools to search the US NPI registry for real healthcare providers.
If a user asks about doctors, hospitals, or network status, use your tools!
1. Always use `search_us_healthcare_providers` to find the provider first.
2. If they ask if the provider is in-network, immediately pass the NPI to `check_provider_network_status`.
3. Present the findings clearly to the user."""


async def chat_node(state: AgentState) -> dict:
    """
    Handle a patient's chat question with RAG-powered response.
    """
    logger.info("Agent 5 (Chat): Processing chat message")

    messages = state.get("messages", [])
    if not messages:
        return {"current_phase": "chat"}

    # Get the latest user message
    last_message = messages[-1]
    user_query = last_message.content if hasattr(last_message, 'content') else str(last_message)

    try:
        # ── RAG Retrieval ─────────────────────────────────────────
        query_embedding = await generate_embedding(user_query)
        rag_results = await search_knowledge_base(
            query_embedding=query_embedding,
            match_count=4,
        )

        rag_context = ""
        if rag_results:
            rag_context = "\n\nRELEVANT KNOWLEDGE BASE EXCERPTS:\n" + "\n---\n".join([
                f"[{r['concept_id']}] {r['title']}\n{r['semantic_summary']}"
                for r in rag_results
            ])

        # ── Include pipeline context if available ─────────────────
        pipeline_context = ""
        if state.get("policy_profile"):
            from app.models.policy import PolicyProfile
            policy = PolicyProfile(**state["policy_profile"])
            pipeline_context += (
                f"\n\nPATIENT'S CURRENT POLICY:\n"
                f"- {policy.plan_name} ({policy.carrier_name})\n"
                f"- Type: {policy.plan_type.value}\n"
                f"- Deductible: ${policy.in_network_deductible_individual:,.2f} "
                f"(${policy.deductible_met:,.2f} met)\n"
                f"- OOP Max: ${policy.in_network_oop_max_individual:,.2f} "
                f"(${policy.oop_met:,.2f} met)\n"
            )

        if state.get("cost_breakdown"):
            from app.models.claim import CostBreakdown
            cost = CostBreakdown(**state["cost_breakdown"])
            pipeline_context += (
                f"\n\nLATEST CLAIM RESULT:\n"
                f"- Status: {cost.claim_status.value}\n"
                f"- Patient owes: ${cost.total_patient_responsibility:,.2f}\n"
                f"- Insurer pays: ${cost.total_insurer_payout:,.2f}\n"
            )

        # ── Generate response ─────────────────────────────────────
        tools = [ProviderSearchTool(), NetworkStatusTool()]
        llm = get_llm(TaskType.CHAT, temperature=0.4).bind_tools(tools)

        # Build conversation history (keep last 10 messages for context)
        chat_messages = [SystemMessage(content=CHAT_SYSTEM_PROMPT + rag_context + pipeline_context)]
        for msg in messages[-10:]:
            if hasattr(msg, 'type'):
                if msg.type == "human":
                    chat_messages.append(HumanMessage(content=msg.content))
                elif msg.type == "ai":
                    chat_messages.append(AIMessage(content=msg.content))
                elif msg.type == "tool":
                    chat_messages.append(ToolMessage(content=msg.content, tool_call_id=msg.tool_call_id))
            else:
                chat_messages.append(HumanMessage(content=str(msg)))

        # Tool execution loop (max 3 steps)
        max_steps = 3
        current_step = 0
        while current_step < max_steps:
            response = await llm.ainvoke(chat_messages)
            chat_messages.append(response)

            if not response.tool_calls:
                break

            for tool_call in response.tool_calls:
                tool_name = tool_call["name"]
                tool_args = tool_call["args"]
                
                try:
                    if tool_name == "search_us_healthcare_providers":
                        tool_result = ProviderSearchTool().invoke(tool_args)
                    elif tool_name == "check_provider_network_status":
                        tool_result = NetworkStatusTool().invoke(tool_args)
                    else:
                        tool_result = f"Error: Unknown tool {tool_name}"
                except Exception as e:
                    tool_result = f"Error executing {tool_name}: {e}"

                chat_messages.append(ToolMessage(
                    content=str(tool_result),
                    tool_call_id=tool_call["id"]
                ))
            
            current_step += 1

        logger.info(f"Agent 5: Chat response generated ({len(response.content)} chars)")

        return {
            "messages": [AIMessage(content=response.content)],
            "current_phase": "chat",
        }

    except Exception as e:
        error_msg = f"Agent 5: Chat failed: {e}"
        logger.error(error_msg, exc_info=True)
        return {
            "messages": [AIMessage(content=(
                "I'm sorry, I encountered an error processing your question. "
                "Please try again or rephrase your question."
            ))],
            "errors": state.get("errors", []) + [error_msg],
            "current_phase": "chat",
        }
