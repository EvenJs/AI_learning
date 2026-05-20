import os
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langgraph.prebuilt import create_react_agent
from langchain_mcp_adapters.client import MultiServerMCPClient
import asyncio

load_dotenv()

async def main():
    # 1. Connect to the MCP server and get tools (NO async with!)
    client = MultiServerMCPClient(
        {
            "weather": {
                "url": "http://localhost:8000/mcp",
                "transport": "streamable_http",
            }
        }
    )

    TOOLS = await client.get_tools()

    # 2. Create a system prompt for the agent

    SYSTEM_PROMPT = (
        "You are a travel agent. Given a destination and travel start/end date, "
        "generate a daily itinerary. For each day, use the get_weather tool to get the weather. "
        "If real weather is not available, please inform the user that the weather is not available. "
        "Include activities, packing tips, and a short checklist."
    )

    print("Before agent.ainvoke()")
    # 3. Set up the agent
    agent = create_react_agent(
        model=ChatOpenAI(model_name="gpt-4o-mini", api_key=os.environ.get("OPENAI_API_KEY")),
        tools=TOOLS,
        prompt=SYSTEM_PROMPT
    )

    # 4. Example user input: destination, start date, end date
    user_input = (
        "I want to travel to Melbourne from 2025-05-20 to 2025-05-22. "
        "Please plan my trip."
    )

    result = await agent.ainvoke({
        "messages": [
            {"role": "user", "content": user_input}
        ]
    })
    print(result)
    print(result["messages"][-1].content)

if __name__ == "__main__":
    print("Starting")
    asyncio.run(main())