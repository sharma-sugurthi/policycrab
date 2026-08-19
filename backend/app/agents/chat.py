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
from app.tools.web_search import WebSearchTool
from langchain_core.messages import ToolMessage

logger = logging.getLogger(__name__)

CHAT_SYSTEM_PROMPT = """You are an AI health insurance assistant for PolicyCrab, specializing in the US healthcare system. You help patients understand their insurance policies, claims, denials, appeals, and rights.

STATUTORY FACT TABLE (FEDERAL RULES):
Treat these deadlines as established facts. Never hedge or express uncertainty about them.
- ERISA Internal Appeal Deadline: 180 days from receipt of denial letter.
- ERISA External Review Request: 4 months after final internal denial.
- ACA Marketplace Appeal: 60 days from notice.
- ACA External Review: 4 months from final internal denial.
- No Surprises Act (NSA) Independent Dispute Resolution: 30 days from initial payment/denial.
- Medicare Part A Appeal (Redetermination): 120 days.
- Medicare Part B Appeal: 120 days.
- Medicaid Fair Hearing: 90 days (federal floor, states may extend).
- Pre-authorization Appeal (Standard): 30 days (ACA-compliant plans).
- Pre-authorization Appeal (Urgent/Expedited): 72 hours.
- Emergency Concurrent Care (Urgent): 24 hours.
- COBRA Election Period: 60 days from notice.
- HIPAA Special Enrollment Period: 30 days (60 days for Medicaid/CHIP events).

PERSONAL CONTEXT: The user's most recent policy profile and/or claim data may be automatically provided below. When it is present, treat it as ground truth about *this specific user* and reference it proactively. Do not ask the user to "upload their policy" if it is already in context. Use their actual deductible, OOP max, plan type, carrier name, and claim status in your answers.

DOMAIN RESTRICTION: You ONLY answer questions about US health insurance. If asked about anything unrelated (cooking, sports, politics, etc.), politely redirect: "I'm specialized in US health insurance. I can help you understand your coverage, claims, denials, or appeals."

ACCURACY RULES:
1. Use the Statutory Fact Table above for standard deadlines without hedging.
2. Use the user's personal policy/claim data (when present) as your PRIMARY source for their specific situation.
3. Use retrieved knowledge base excerpts as your SECONDARY source for regulations & law.
4. If the knowledge base has relevant information, cite it directly.
5. If you're unsure or data doesn't cover the topic, say so honestly, but do not override the statutory facts.
6. NEVER fabricate regulations, deadlines, or dollar amounts.
7. Always specify whether something is federal law vs. state-specific.

TONE: Empathetic, clear, actionable. The patient is likely stressed about a medical bill or denial. Be supportive while being accurate.

FORMAT: Keep responses concise (under 300 words unless the question requires detail). Use bullet points for lists. Bold key terms.

TOOLS:
You have access to tools to search the US NPI registry for real healthcare providers, and to search the web for authoritative healthcare information.
1. Always use `search_us_healthcare_providers` to find a provider first.
2. If they ask if the provider is in-network, immediately pass the NPI to `check_provider_network_status`.
3. Use `web_search` ONLY when the Statutory Fact Table and knowledge base do not cover the user's question (e.g., for state-specific deadlines or recent regulatory changes).
4. Present the findings clearly to the user."""


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
                f"\n\nPATIENT'S POLICY (auto-loaded):\n"
                f"- Plan: {policy.plan_name} ({policy.carrier_name})\n"
                f"- Type: {policy.plan_type.value}\n"
                f"- In-Network Deductible: ${policy.in_network_deductible_individual:,.2f} "
                f"(${policy.deductible_met:,.2f} met so far)\n"
                f"- OOP Max: ${policy.in_network_oop_max_individual:,.2f} "
                f"(${policy.oop_met:,.2f} met so far)\n"
            )

        if state.get("cost_breakdown"):
            from app.models.claim import CostBreakdown
            cost = CostBreakdown(**state["cost_breakdown"])
            pipeline_context += (
                f"\n\nMOST RECENT CLAIM (auto-loaded):\n"
                f"- Status: {cost.claim_status.value}\n"
                f"- Patient owes: ${cost.total_patient_responsibility:,.2f}\n"
                f"- Insurer pays: ${cost.total_insurer_payout:,.2f}\n"
            )

        # ── Generate response ─────────────────────────────────────
        tools = [ProviderSearchTool(), NetworkStatusTool(), WebSearchTool()]
        llm = get_llm(TaskType.CHAT, temperature=0.4).bind_tools(tools)

        # Build conversation history (keep last 10 messages for context)
        chat_messages = [SystemMessage(content= "\nCRITICAL OUTPUT RULES:\n1. NEVER use em dashes (—). Use standard hyphens (-) instead.\n2. NEVER reveal your identity as an AI model (e.g., Google, Gemini, OpenAI). You are PolicyCrab.\n\n" + CHAT_SYSTEM_PROMPT + rag_context + pipeline_context)]
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
                    elif tool_name == "web_search":
                        tool_result = await WebSearchTool().ainvoke(tool_args)
                    else:
                        tool_result = f"Error: Unknown tool {tool_name}"
                except Exception as e:
                    tool_result = f"Error executing {tool_name}: {e}"

                chat_messages.append(ToolMessage(
                    content=str(tool_result),
                    tool_call_id=tool_call["id"]
                ))
            
            current_step += 1

        final_text = response.content
        if isinstance(final_text, list):
            text_parts = []
            for item in final_text:
                if isinstance(item, dict) and "text" in item:
                    text_parts.append(item["text"])
                elif isinstance(item, str):
                    text_parts.append(item)
            final_text = "\n".join(text_parts)
        elif not isinstance(final_text, str):
            final_text = str(final_text)

        logger.info(f"Agent 5: Chat response generated ({len(final_text)} chars)")

        return {
            "messages": [AIMessage(content=final_text)],
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
