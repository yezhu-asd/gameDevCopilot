"use strict";

const $ = (id) => document.getElementById(id);

let currentJobId = null;
let pollTimer = null;

const EVENT_LABELS = {
    start: "开始生成",
    rag: "RAG 知识库检索中",
    generating: "Agent 生成代码中",
    generated: "Agent 已生成文件",
    verifying: "Godot 无头验证中",
    fixing: "自动修复中",
    done: "完成",
};

function addTimelineItem(event) {
    const li = document.createElement("li");
    const dot = document.createElement("span");
    dot.className = "dot";
    li.appendChild(dot);

    const text = document.createElement("span");
    text.className = "text";
    text.textContent = EVENT_LABELS[event] || event;
    li.appendChild(text);

    const meta = document.createElement("span");
    meta.className = "meta";
    li.appendChild(meta);

    $("timeline").appendChild(li);
    return li;
}

function markAllDone() {
    // Close every active step so only the current one pulses.
    document.querySelectorAll("#timeline li.active").forEach((li) => {
        li.classList.remove("active");
        li.classList.add("done");
    });
}

function renderEvent(event, data, li, isActive) {
    const text = li.querySelector(".text");
    const meta = li.querySelector(".meta");

    if (event === "start") {
        li.classList.add("done");
        meta.textContent = "✓";
    } else if (event === "phase") {
        if (data.phase === "rag" || data.phase === "generating") {
            li.classList.add("active");
            meta.textContent = "";
        }
    } else if (event === "generated") {
        li.classList.add("done");
        meta.textContent = `${data.n_files} 个文件`;
    } else if (event === "verifying") {
        if (isActive) {
            li.classList.add("active");
            meta.textContent = `第 ${data.round} 轮 (${data.action})`;
        } else {
            li.classList.remove("active");
            li.classList.add("done");
            meta.textContent = `第 ${data.round} 轮 ✓`;
        }
    } else if (event === "fixing") {
        li.classList.add("active");
        meta.textContent = `第 ${data.round} 轮 · ${data.errors.length} 个错误`;
    } else if (event === "done") {
        li.classList.remove("active");
        li.classList.add(data.success ? "done" : "failed");
        meta.textContent = data.success ? "✅ 成功" : "❌ 失败";
    }
}

let processedEvents = 0;

function pollJob() {
    fetch(`/api/jobs/${currentJobId}`)
        .then((r) => r.json())
        .then((job) => {
            const events = job.events;
            for (let i = processedEvents; i < events.length; i++) {
                const { event, data } = events[i];
                handleEvent(event, data);
            }
            processedEvents = Math.max(processedEvents, events.length);

            $("status-hint").textContent = `状态: ${job.status}`;
            if (job.status === "done") {
                $("generate-btn").disabled = false;
                $("stop-btn").disabled = true;
                clearInterval(pollTimer);
                $("status-hint").textContent = job.success ? "✅ 生成成功" : "❌ 生成失败";
                if (job.success) loadFiles();
            } else if (job.status === "failed") {
                $("generate-btn").disabled = false;
                $("stop-btn").disabled = true;
                clearInterval(pollTimer);
                $("status-hint").textContent = `❌ 失败: ${job.error || "生成失败"}`;
            }
        })
        .catch((e) => {
            console.error("poll error", e);
        });
}

// Maps each verifying event (per round) to its timeline <li> so the later
// `verified` event can mark it done.
const verifyingItems = [];
let lastPhaseLi = null;

function handleEvent(event, data) {
    if (event === "start") {
        const li = addTimelineItem("start");
        renderEvent("start", data, li, false);
    } else if (event === "phase") {
        // Close any active step, then open the new phase line.
        markAllDone();
        const li = addTimelineItem(data.phase);
        renderEvent("phase", data, li, true);
        lastPhaseLi = li;
    } else if (event === "generated") {
        markAllDone();
    } else if (event === "verifying") {
        markAllDone();
        const li = addTimelineItem("verifying");
        renderEvent("verifying", data, li, true);
        verifyingItems.push(li);
    } else if (event === "verified") {
        markAllDone();
        const li = verifyingItems.shift();
        if (li) renderEvent("verifying", data, li, false); // mark done
    } else if (event === "fixing") {
        markAllDone();
        const li = addTimelineItem("fixing");
        renderEvent("fixing", data, li, true);
    } else if (event === "done") {
        markAllDone();
        const li = addTimelineItem("done");
        renderEvent("done", data, li, false);
    }
}

function loadFiles() {
    fetch(`/api/jobs/${currentJobId}/files`)
        .then((r) => r.json())
        .then((data) => {
            $("result-section").classList.remove("hidden");
            $("result-dir").textContent = data.dir || "";
            const tree = $("file-tree");
            const content = $("file-content");
            tree.innerHTML = "";
            content.textContent = "";
            data.files.forEach((f, i) => {
                const li = document.createElement("li");
                li.textContent = f.path;
                li.dataset.path = f.path;
                if (i === 0) {
                    li.classList.add("selected");
                    content.textContent = f.content;
                }
                li.addEventListener("click", () => {
                    tree.querySelectorAll("li").forEach((n) => n.classList.remove("selected"));
                    li.classList.add("selected");
                    content.textContent = f.content;
                });
                tree.appendChild(li);
            });
        });
}

$("generate-btn").addEventListener("click", () => {
    const spec = $("spec-input").value.trim();
    if (!spec) {
        $("status-hint").textContent = "请输入游戏描述";
        return;
    }
    $("generate-btn").disabled = true;
    $("stop-btn").disabled = false;
    $("status-hint").textContent = "提交中...";
    $("result-section").classList.add("hidden");
    $("progress-section").classList.remove("hidden");
    $("timeline").innerHTML = "";
    processedEvents = 0;
    verifyingItems.length = 0;
    lastPhaseLi = null;

    fetch("/api/generate", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ spec }),
    })
        .then((r) => r.json())
        .then((data) => {
            if (data.error) {
                $("status-hint").textContent = `❌ ${data.error}`;
                $("generate-btn").disabled = false;
                $("stop-btn").disabled = true;
                return;
            }
            currentJobId = data.job_id;
            pollTimer = setInterval(pollJob, 1500);
            pollJob();
        })
        .catch((e) => {
            $("status-hint").textContent = "❌ 请求失败";
            $("generate-btn").disabled = false;
            $("stop-btn").disabled = true;
            console.error(e);
        });
});

$("stop-btn").addEventListener("click", () => {
    if (pollTimer) clearInterval(pollTimer);
    currentJobId = null;
    $("generate-btn").disabled = false;
    $("stop-btn").disabled = true;
    $("status-hint").textContent = "已停止";
});
