const $ = (id) => document.getElementById(id);

const state = {
    story: null,
    busy: false,
    recent: [],
    toastTimer: null
};

const STORAGE_KEY = "storytelling-studio-recent-v1";

function loadRecent() {
    try {
        const saved = JSON.parse(localStorage.getItem(STORAGE_KEY) || "[]");
        state.recent = Array.isArray(saved) ? saved.slice(0, 15) : [];
    } catch {
        state.recent = [];
    }
    renderRecent();
}

function saveRecent() {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(state.recent.slice(0, 15)));
    renderRecent();
}

function rememberStory(story) {
    state.recent = [
        { id: story.id, title: story.title },
        ...state.recent.filter(item => item.id !== story.id)
    ].slice(0, 15);
    saveRecent();
}

function toast(message) {
    const element = $("toast");
    element.textContent = message;
    element.classList.add("show");
    clearTimeout(state.toastTimer);
    state.toastTimer = setTimeout(() => element.classList.remove("show"), 3500);
}

function setBusy(active, title = "Working on your story...", description = "") {
    state.busy = active;
    $("busyOverlay").classList.toggle("hidden", !active);
    $("busyTitle").textContent = title;
    $("busyDescription").textContent = description;

    ["newStoryButton", "welcomeNewButton", "refreshButton",
     "saveButton", "generateButton"].forEach(id => {
        $(id).disabled = active;
    });
}

function setConnection(connected) {
    $("connectionStatus").innerHTML = connected
        ? '<span class="status-dot"></span> Cloud connected'
        : '<span style="color:#fb8585">●</span> API unavailable';
}

async function api(path, options = {}) {
    const response = await fetch(path, {
        ...options,
        headers: {
            "Content-Type": "application/json",
            ...(options.headers || {})
        }
    });

    const body = await response.json().catch(() => ({}));

    if (!response.ok) {
        const error = new Error(
            typeof body.detail === "string"
                ? body.detail
                : JSON.stringify(body.detail || body)
        );
        error.status = response.status;
        throw error;
    }

    return body;
}

function renderRecent() {
    const container = $("storyList");
    container.replaceChildren();

    if (!state.recent.length) {
        const empty = document.createElement("p");
        empty.className = "muted small";
        empty.textContent = "No recently opened stories.";
        container.append(empty);
        return;
    }

    state.recent.forEach(item => {
        const button = document.createElement("button");
        button.className = "story-item";
        button.classList.toggle(
            "active",
            state.story && state.story.id === item.id
        );

        const title = document.createElement("span");
        title.textContent = item.title;

        const subtitle = document.createElement("small");
        subtitle.textContent = "Open story";

        button.append(title, subtitle);
        button.addEventListener("click", () => loadStory(item.id));
        container.append(button);
    });
}

function updateWordCount() {
    const text = $("storyEditor").value.trim();
    const count = text ? text.split(/\s+/).length : 0;
    $("wordCount").textContent = `${count} words`;
}

function renderStory(story) {
    state.story = story;

    $("welcomePanel").classList.add("hidden");
    $("workspace").classList.remove("hidden");

    $("pageHeading").textContent = story.title;
    $("storyTitle").textContent = story.title;
    $("storyEditor").value = story.content;
    $("versionLabel").textContent = `Version ${story.version}`;
    $("updatedLabel").textContent =
        `Updated ${new Date(story.updated_at).toLocaleString()}`;
    $("saveStatus").textContent = "Loaded";

    $("workflowResult").classList.add("hidden");

    updateWordCount();
    rememberStory(story);
}

async function loadStory(id) {
    if (state.busy) return;

    try {
        setBusy(true, "Loading story...", "Retrieving canonical story state.");
        const story = await api(`/stories/${encodeURIComponent(id)}`);
        renderStory(story);
        setConnection(true);
    } catch (error) {
        toast(`Could not load story: ${error.message}`);
        if (error.status === 404) {
            state.recent = state.recent.filter(item => item.id !== id);
            saveRecent();
        }
    } finally {
        setBusy(false);
    }
}

function openCreateDialog() {
    $("createForm").reset();
    $("createDialog").showModal();
}

async function createStory(event) {
    event.preventDefault();
    if (state.busy) return;

    const title = $("newTitle").value.trim();
    const initialContent = $("initialContent").value;

    if (!title) {
        toast("Please enter a story title.");
        return;
    }

    try {
        setBusy(true, "Creating your story...", "Saving the initial canonical state.");
        const story = await api("/stories", {
            method: "POST",
            body: JSON.stringify({
                title,
                initial_content: initialContent
            })
        });

        $("createDialog").close();
        renderStory(story);
        setConnection(true);
        toast("Story created successfully.");
    } catch (error) {
        toast(`Story creation failed: ${error.message}`);
    } finally {
        setBusy(false);
    }
}

async function refreshStory() {
    if (!state.story || state.busy) return;
    await loadStory(state.story.id);
    if (state.story) toast("Latest canonical story retrieved.");
}

async function saveRevision() {
    if (!state.story || state.busy) return;

    if ($("storyEditor").value === state.story.content) {
        toast("There are no unsaved changes.");
        return;
    }

    try {
        setBusy(true, "Saving revision...", "Checking the expected story version.");

        const result = await api(
            `/stories/${encodeURIComponent(state.story.id)}/revisions`,
            {
                method: "POST",
                body: JSON.stringify({
                    expected_version: state.story.version,
                    new_content: $("storyEditor").value,
                    agent_id: "human-editor",
                    event_payload: {
                        source: "storytelling-studio",
                        operation: "manual-revision"
                    }
                })
            }
        );

        await loadStoryWithoutOverlay(state.story.id);
        toast(`Revision committed as version ${result.committed_version}.`);
    } catch (error) {
        if (error.status === 409) {
            toast("Version conflict. Refreshing the latest canonical story.");
            await loadStoryWithoutOverlay(state.story.id);
        } else {
            toast(`Revision failed: ${error.message}`);
        }
    } finally {
        setBusy(false);
    }
}

async function loadStoryWithoutOverlay(id) {
    const story = await api(`/stories/${encodeURIComponent(id)}`);
    renderStory(story);
}

async function generateContinuation() {
    if (!state.story || state.busy) return;

    const prompt = $("userPrompt").value.trim();

    if (prompt.length < 10) {
        toast("Please provide at least 10 characters of creative direction.");
        return;
    }

    const storyId = state.story.id;
    const expectedVersion = state.story.version;

    $("workflowResult").classList.add("hidden");

    try {
        setBusy(
            true,
            "AI agents are developing your story...",
            "Generating proposals, evaluating narrative coherence and committing the approved result."
        );

        const result = await api(
            `/stories/${encodeURIComponent(storyId)}/agentic-revisions`,
            {
                method: "POST",
                body: JSON.stringify({
                    expected_version: expectedVersion,
                    user_request: prompt
                })
            }
        );

        if (result.status === "committed") {
            await loadStoryWithoutOverlay(storyId);
            renderWorkflowResult(result);
            toast(`AI continuation committed as version ${result.committed_version}.`);
        } else {
            toast(`Workflow returned status: ${result.status}`);
        }
    } catch (error) {
        if (error.status === 409) {
            toast("The story changed during generation. Refreshing canonical state.");
            await loadStoryWithoutOverlay(storyId);
        } else {
            toast(`AI workflow failed: ${error.message}`);
        }
    } finally {
        setBusy(false);
    }
}

function renderWorkflowResult(result) {
    const provenance = result.provenance || {};
    const critic = provenance.critic_evaluation || {};

    $("workflowStatus").textContent = result.status;
    $("criticScore").textContent =
        result.critic_score === null ? "—" : `${result.critic_score}/100`;
    $("criticEvaluations").textContent = result.critic_evaluations ?? "—";
    $("revisionAttempts").textContent = result.revision_attempts ?? "—";

    $("evaluationExplanation").textContent =
        critic.explanation || "No critic explanation was returned.";

    $("provenance").textContent = JSON.stringify(provenance, null, 2);

    $("workflowResult").classList.remove("hidden");
}

async function checkHealth() {
    try {
        await api("/health");
        setConnection(true);
    } catch {
        setConnection(false);
    }
}

$("newStoryButton").addEventListener("click", openCreateDialog);
$("welcomeNewButton").addEventListener("click", openCreateDialog);
$("closeDialogButton").addEventListener("click", () => $("createDialog").close());
$("createForm").addEventListener("submit", createStory);
$("refreshButton").addEventListener("click", refreshStory);
$("saveButton").addEventListener("click", saveRevision);
$("generateButton").addEventListener("click", generateContinuation);
$("storyEditor").addEventListener("input", updateWordCount);

loadRecent();
checkHealth();
setInterval(checkHealth, 30000);

