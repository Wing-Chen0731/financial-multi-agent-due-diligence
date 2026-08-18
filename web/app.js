const $ = (selector) => document.querySelector(selector);
const input = $("#query-input");
const submitButton = $("#submit-button");
const resultEmpty = $("#result-empty");
const resultContent = $("#result-content");
const toast = $("#toast");

function providerLabel(provider) {
  if (provider === "ollama") return "Ollama / Local";
  if (provider === "demo") return "Demo / Offline";
  if (provider === "openrouter") return "OpenRouter / Remote";
  if (provider === "huggingface" || provider === "hf") return "Hugging Face / Remote";
  return `${provider} / API`;
}

async function loadRuntimeStatus() {
  try {
    const response = await fetch("/readiness");
    const status = await response.json();
    const ready = status.status === "ready";
    $("#model-status").textContent = ready ? "模型连接正常" : "运行时未就绪";
    $("#model-label").textContent = providerLabel(status.provider);
    $("#model-meta").textContent = `${status.model} · ${status.execution_mode} mode`;
  } catch (error) {
    $("#model-status").textContent = "后端未连接";
    $("#model-label").textContent = "后端未连接";
    $("#model-meta").textContent = "请启动本地服务";
  }
}

const agents = {
  supervisor: ["Supervisor", "任务分流 · 识别问题类型"],
  data_collector: ["Data Collector", "采集客户资料与知识库依据"],
  risk_analyzer: ["Risk Analyzer", "识别风险点与缺失材料"],
  compliance_checker: ["Compliance Checker", "对照检索依据进行审查"],
  report_writer: ["Report Writer", "汇总结论并添加安全护栏"],
};

const taskNames = {
  general_chat: "GENERAL CHAT",
  due_diligence: "DUE DILIGENCE",
  compliance_query: "COMPLIANCE QUERY",
  investment_query: "SAFEGUARD TEST",
};

function showToast(message) {
  toast.textContent = message;
  toast.classList.add("show");
  window.clearTimeout(showToast.timer);
  showToast.timer = window.setTimeout(() => toast.classList.remove("show"), 2800);
}

function renderTimeline(trace, taskType, isLoading = false) {
  const timeline = $("#timeline");
  if (!trace || !trace.length) {
    timeline.replaceChildren();
    const empty = document.createElement("div");
    empty.className = "timeline-empty";
    empty.textContent = "运行分析后，这里会显示 Agent 协作过程。";
    timeline.appendChild(empty);
    return;
  }
  timeline.replaceChildren();
  trace.forEach((node, index) => {
    const [name, description] = agents[node] || [node, "处理状态"];
    const active = isLoading && index === trace.length - 1;
    const item = document.createElement("div");
    item.className = "timeline-item";
    const dot = document.createElement("span");
    dot.className = "timeline-dot";
    dot.textContent = active ? "…" : "✓";
    const copy = document.createElement("div");
    const title = document.createElement("div");
    title.className = "timeline-name";
    title.textContent = name;
    const detail = document.createElement("div");
    detail.className = "timeline-description";
    detail.textContent = description;
    copy.append(title, detail);
    const status = document.createElement("span");
    status.className = "timeline-status";
    status.textContent = active ? "RUNNING" : "DONE";
    item.append(dot, copy, status);
    timeline.appendChild(item);
  });
  $("#trace-title").textContent = isLoading ? "正在执行分析链" : `${taskNames[taskType] || "ANALYSIS"} 已完成`;
  $("#trace-subtitle").textContent = `${trace.length} 个节点已写入执行轨迹`;
  $("#trace-time").textContent = new Date().toLocaleTimeString("zh-CN", { hour: "2-digit", minute: "2-digit" });
}

function renderSources(sources) {
  const block = $("#sources-block");
  const list = $("#sources-list");
  $("#source-count").textContent = `${sources.length} source${sources.length === 1 ? "" : "s"}`;
  if (!sources.length) {
    block.classList.add("hidden");
    return;
  }
  block.classList.remove("hidden");
  list.replaceChildren();
  sources.forEach((source) => {
    const row = document.createElement("div");
    row.className = "source-row";
    const title = document.createElement("strong");
    title.title = String(source.source || "未知来源");
    title.textContent = String(source.source || "未知来源");
    const snippet = document.createElement("span");
    snippet.textContent = String(source.snippet || "已纳入本次分析");
    row.append(title, snippet);
    list.appendChild(row);
  });
}

function renderDataStatus(result) {
  const card = $("#data-status-card");
  const status = result.customer_data_status || result.collected_data?.customer_data_status;
  if (!status || status.status !== "not_found") {
    card.classList.add("hidden");
    return;
  }

  card.classList.remove("hidden");
  $("#data-status-label").textContent = status.label || "资料待补充";
  $("#data-status-source").textContent = status.source || "数据源未知";
  $("#data-status-message").textContent = `${status.customer_name || "该客户"} 未在当前 CRM 数据源中找到。系统不会补写企业事实，补件完成前不能形成确定性的授信结论。`;

  const materials = $("#missing-materials-list");
  materials.replaceChildren();
  (status.missing_materials || []).forEach((item) => {
    const row = document.createElement("li");
    const name = document.createElement("strong");
    name.textContent = item.name || "待补材料";
    const detail = document.createElement("span");
    detail.textContent = item.detail || "请补充可核验材料";
    row.append(name, detail);
    materials.appendChild(row);
  });

  const actions = $("#data-status-actions");
  actions.replaceChildren();
  (status.next_actions || []).forEach((action) => {
    const row = document.createElement("li");
    row.textContent = action;
    actions.appendChild(row);
  });
}

function appendInlineMarkdown(container, value) {
  const pattern = /(\*\*[^*]+\*\*|`[^`]+`|\*[^*]+\*)/g;
  let cursor = 0;
  let match;

  while ((match = pattern.exec(value)) !== null) {
    if (match.index > cursor) {
      container.appendChild(document.createTextNode(value.slice(cursor, match.index)));
    }

    const token = match[0];
    let tag = "span";
    let text = token;
    if (token.startsWith("**")) {
      tag = "strong";
      text = token.slice(2, -2);
    } else if (token.startsWith("`")) {
      tag = "code";
      text = token.slice(1, -1);
    } else if (token.startsWith("*")) {
      tag = "em";
      text = token.slice(1, -1);
    }

    const element = document.createElement(tag);
    element.textContent = text;
    container.appendChild(element);
    cursor = pattern.lastIndex;
  }

  if (cursor < value.length) {
    container.appendChild(document.createTextNode(value.slice(cursor)));
  }
}

function renderMarkdown(markdown) {
  const container = $("#answer-text");
  container.replaceChildren();
  const lines = String(markdown || "").replace(/\r\n?/g, "\n").split("\n");
  let index = 0;

  while (index < lines.length) {
    const line = lines[index];
    if (!line.trim()) {
      index += 1;
      continue;
    }

    const heading = line.match(/^(#{1,6})\s+(.+)$/);
    if (heading) {
      const element = document.createElement(`h${Math.min(heading[1].length, 4)}`);
      appendInlineMarkdown(element, heading[2]);
      container.appendChild(element);
      index += 1;
      continue;
    }

    if (/^\s*(---+|\*\*\*+)\s*$/.test(line)) {
      container.appendChild(document.createElement("hr"));
      index += 1;
      continue;
    }

    const ordered = line.match(/^\s*\d+\.\s+(.+)$/);
    if (ordered) {
      const list = document.createElement("ol");
      while (index < lines.length) {
        const item = lines[index].match(/^\s*\d+\.\s+(.+)$/);
        if (!item) break;
        const listItem = document.createElement("li");
        appendInlineMarkdown(listItem, item[1]);
        list.appendChild(listItem);
        index += 1;
      }
      container.appendChild(list);
      continue;
    }

    const unordered = line.match(/^\s*[-*]\s+(.+)$/);
    if (unordered) {
      const list = document.createElement("ul");
      while (index < lines.length) {
        const item = lines[index].match(/^\s*[-*]\s+(.+)$/);
        if (!item) break;
        const listItem = document.createElement("li");
        appendInlineMarkdown(listItem, item[1]);
        list.appendChild(listItem);
        index += 1;
      }
      container.appendChild(list);
      continue;
    }

    const paragraph = document.createElement("p");
    appendInlineMarkdown(paragraph, line.trim());
    container.appendChild(paragraph);
    index += 1;
  }
}

function renderResult(result) {
  resultEmpty.classList.add("hidden");
  resultContent.classList.remove("hidden");
  renderMarkdown(result.response || "系统未返回可展示的结论。");
  renderDataStatus(result);
  $("#result-type").textContent = taskNames[result.task_type] || "ANALYSIS";
  $("#prompt-version").textContent = `Prompt ${result.prompt_version || "unknown"}`;
  $("#skills-label").textContent = `${(result.selected_skills || []).length} Skills active`;
  if (result.runtime) {
    $("#model-label").textContent = providerLabel(result.runtime.provider);
    $("#model-meta").textContent = `${result.runtime.model} · ${result.runtime.execution_mode} mode`;
  }
  const confidence = Math.round((result.confidence || 0) * 100);
  $("#confidence-value").textContent = `${confidence}%`;
  $("#confidence-bar").style.width = `${confidence}%`;
  $("#review-flag").textContent = result.need_human_review ? "待人工复核" : "辅助结果";
  $("#review-flag").style.color = result.need_human_review ? "#ad7c3b" : "#5c9876";
  $("#review-flag").style.background = result.need_human_review ? "#fff5e3" : "#edf7f0";
  renderSources(result.sources || []);
  renderTimeline(result.trace || [], result.task_type);
}

async function runAnalysis() {
  const message = input.value.trim();
  if (!message) {
    showToast("先输入一个问题，或选择下方的演示场景。");
    input.focus();
    return;
  }
  submitButton.disabled = true;
  submitButton.querySelector("span:first-child").textContent = "分析中…";
  renderTimeline(["supervisor", "data_collector", "risk_analyzer", "compliance_checker", "report_writer"], "", true);
  try {
    const response = await fetch("/chat", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ message, session_id: "portfolio-demo" }) });
    if (!response.ok) throw new Error("API unavailable");
    renderResult(await response.json());
  } catch (error) {
    showToast("暂时无法连接分析服务，请确认已启动 FastAPI。");
    $("#trace-title").textContent = "等待服务连接";
    $("#trace-subtitle").textContent = "前端已就绪，后端服务尚未响应";
  } finally {
    submitButton.disabled = false;
    submitButton.querySelector("span:first-child").textContent = "运行分析";
  }
}

submitButton.addEventListener("click", runAnalysis);
input.addEventListener("keydown", (event) => {
  if ((event.metaKey || event.ctrlKey) && event.key === "Enter") runAnalysis();
});
document.querySelectorAll("[data-query]").forEach((button) => {
  button.addEventListener("click", () => {
    input.value = button.dataset.query;
    input.focus();
    runAnalysis();
  });
});

loadRuntimeStatus();
