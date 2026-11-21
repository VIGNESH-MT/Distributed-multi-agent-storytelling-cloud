from app.agents.graph import run_story_workflow


def main():
    print("=" * 60)
    print("DISTRIBUTED STORYTELLING - MULTI-AGENT TEST")
    print("=" * 60)

    result = run_story_workflow(
        story_title="The Lighthouse Signal",
        current_story=(
            "Mira, an apprentice lighthouse keeper, discovers "
            "a mysterious signal coming from an abandoned island. "
            "Her mentor Elias warns her never to answer it."
        ),
        user_request=(
            "Develop the mystery while preserving the established "
            "characters and their motivations. Include meaningful "
            "character dialogue and a meaningful discovery."
        ),
    )

    print("\n========== PLOT AGENT ==========")
    print(result["plot_proposal"].model_dump_json(indent=2))

    print("\n========== CHARACTER AGENT ==========")
    print(result["character_proposal"].model_dump_json(indent=2))

    print("\n========== CRITIC AGENT ==========")
    print(result["critic_evaluation"].model_dump_json(indent=2))

    print("\n========== WORKFLOW RESULT ==========")
    print("Status:", result["workflow_status"])
    print("Critic evaluations:", result["critic_evaluations"])
    print("Actual revision attempts:", result["revision_attempts"])

    if result["workflow_status"] == "approved":
        print("RESULT: MULTI-AGENT WORKFLOW APPROVED")
    elif result["workflow_status"] == "rejected":
        print("RESULT: PROPOSAL REJECTED AFTER BOUNDED REVIEW")
    else:
        raise RuntimeError("Unexpected workflow termination state.")


if __name__ == "__main__":
    main()
