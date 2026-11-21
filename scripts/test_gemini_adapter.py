from app.agents.model import invoke_model


def main() -> None:
    print("========== GEMINI ADAPTER TEST ==========")

    result = invoke_model(
        "You are a concise test assistant. "
        "Reply with exactly: STORY_AGENT_ADAPTER_SUCCESS"
    )

    print("\nModel response:")
    print(result)

    if "STORY_AGENT_ADAPTER_SUCCESS" not in result:
        raise SystemExit("FAILED: Unexpected model response.")

    print("\nRESULT: GEMINI ADAPTER SUCCESSFUL")


if __name__ == "__main__":
    main()
