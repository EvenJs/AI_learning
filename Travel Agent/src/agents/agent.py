import datetime
import operator
import os
from typing import Annotated, TypedDict

from dotenv import load_dotenv
from langchain_core.messages import AnyMessage, SystemMessage, ToolMessage
from langchain_openai import ChatOpenAI
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, StateGraph

from agents.tools.flights_finder import flights_finder
from agents.tools.hotels_finder import hotels_finder
from agents.tools.weather_check import weather_check

_ = load_dotenv()

CURRENT_YEAR = datetime.datetime.now().year


class AgentState(TypedDict):
    messages: Annotated[list[AnyMessage], operator.add]


TOOLS_SYSTEM_PROMPT = f"""You are an expert AI travel assistant specializing in personalized trip planning for Australia and New Zealand destinations.

Core Responsibilities:
1. Use available tools proactively to gather accurate, up-to-date information (flights, hotels, weather)
2. Create comprehensive daily itineraries that match user energy levels (Relaxed/Balanced/Active)
3. Respect user budget constraints when filtering and recommending options
4. Provide structured, readable outputs with clear sections and formatting

Tool Usage Guidelines:
- Always call weather_check for the destination to provide accurate weather forecasts
- When searching hotels, use the specific location provided in the query (e.g., "Melbourne CBD", "Sydney beachfront")
- Make sequential or parallel tool calls as needed to gather complete information
- If a tool returns an error, acknowledge it and continue planning with available information
- Current year: {CURRENT_YEAR}

Output Format Requirements:
- Structure flight options as "Flight Option 1:", "Flight Option 2:", etc.
- Structure hotel options as "Hotel Option 1:", "Hotel Option 2:", etc.
- Always include prices with currency clearly specified (e.g., "$250 USD" or "$350 AUD")
- For hotels, include: Name, Rating, Price per night, Total price, Location, and website link
- For flights, include: Airline, Flight number, Departure time, Arrival time, Duration, Number of stops, and Price

Hotel Output Example:
Hotel Option 1:
Name: Grand Hotel Melbourne
Rating: 4.5/5
Price: $581 per night
Total: $3,488 USD
Location: Melbourne CBD
Website: [hotel website link]

Flight Output Example:
Flight Option 1:
Airline: Qantas
Flight Number: QF123
Departure: 08:00 AM | Arrival: 10:30 AM
Duration: 2h 30m
Stops: Direct
Price: $250 USD

Budget Handling:
- When a budget is specified in AUD, note that tool APIs may use USD
- Filter and recommend options that fit within the specified budget
- If no options fit the budget, explain this clearly and suggest the closest alternatives

Error Handling:
- If flight or hotel information cannot be retrieved, clearly indicate this in your response
- Continue generating other parts of the travel plan (itinerary, attractions, weather, packing tips)
- Provide helpful alternatives and suggestions based on general knowledge when tools fail
"""

TOOLS = [flights_finder, hotels_finder, weather_check]


class AgentError(Exception):
    """Base exception for agent errors"""
    pass

class ToolExecutionError(AgentError):
    """Exception for tool execution errors"""
    pass


class Agent:
    def __init__(self):
        self._tools = {t.name: t for t in TOOLS}
        self._tools_llm = ChatOpenAI(
            model_name=os.environ.get('OPENAI_MODEL', 'gpt-4o'),
            api_key=os.environ.get('OPENAI_API_KEY'),
        ).bind_tools(TOOLS)

        builder = StateGraph(AgentState)
        builder.add_node('call_tools_llm', self.call_tools_llm)
        builder.add_node('invoke_tools', self.invoke_tools)
        builder.set_entry_point('call_tools_llm')

        builder.add_conditional_edges('call_tools_llm', Agent.exists_action, {'more_tools': 'invoke_tools', 'done': END})
        builder.add_edge('invoke_tools', 'call_tools_llm')
        memory = MemorySaver()
        self.graph = builder.compile(checkpointer=memory)

        self._max_retries = 3

    @staticmethod
    def exists_action(state: AgentState):
        result = state['messages'][-1]
        if hasattr(result, 'tool_calls') and len(result.tool_calls) > 0:
            return 'more_tools'
        return 'done'

    def call_tools_llm(self, state: AgentState):
        messages = state['messages']
        messages = [SystemMessage(content=TOOLS_SYSTEM_PROMPT)] + messages
        message = self._tools_llm.invoke(messages)
        return {'messages': [message]}

    def invoke_tools(self, state: AgentState):
        tool_calls = state['messages'][-1].tool_calls
        results = []
        failed_tools = []

        # Process each tool call
        for tool_call in tool_calls:
            tool_name = tool_call['name']
            tool_id = tool_call['id']

            try:
                if tool_name not in self._tools:
                    raise ToolExecutionError(f"Tool '{tool_name}' not found")

                result = self._tools[tool_name].invoke(tool_call['args'])

                # Handle error responses from tools
                if isinstance(result, dict) and 'error' in result:
                    failed_tools.append(tool_name)
                    error_msg = self._format_error_message(tool_name, result['error'])
                    result = error_msg

                results.append(ToolMessage(tool_call_id=tool_id, name=tool_name, content=str(result)))

            except Exception as e:
                failed_tools.append(tool_name)
                error_msg = self._format_error_message(tool_name, str(e))
                results.append(ToolMessage(tool_call_id=tool_id, name=tool_name, content=error_msg))

        # Note: Removed the error count tracking as it persisted across requests
        # Tools now fail gracefully with error messages that the LLM can handle
        # The LLM will continue planning with available information per the system prompt

        return {'messages': results}

    def _format_error_message(self, tool_name: str, error: str) -> str:
        """Format error messages consistently"""
        return f"[{tool_name.upper()} ERROR] {error}. The assistant will continue with available information."