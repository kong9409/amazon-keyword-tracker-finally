const form = document.querySelector("#captureForm");
const toast = document.querySelector("#toast");
const runButton = document.querySelector("#runCapture");
const saveDailyButton = document.querySelector("#saveDaily");
const testExcelButton = document.querySelector("#testExcelBtn");
const historyBody = document.querySelector("#historyBody");
const recordCount = document.querySelector("#recordCount");
const latestDate = document.querySelector("#latestDate");
const larkFields = document.querySelector("#larkFields");
const sourceBadge = document.querySelector("#sourceBadge");
const marketplaceSelect = document.querySelector("#marketplaceSelect");
const marketplaceName = document.querySelector("#marketplaceName");
const domain = document.querySelector("#domain");
const postalCode = document.querySelector("#postalCode");
const marketHint = document.querySelector("#marketHint");
const progressTitle = document.querySelector("#progressTitle");
const progressSub = document.querySelector("#progressSub");
const progressPct = document.querySelector("#progressPct");
const progressFill = document.querySelector("#progressFill");
const logBox = document.querySelector("#logBox");
const resultLinks = document.querySelector("#resultLinks");
const OWNER_KEY = "amazonKeywordTrackerOwnerId";

const MARKETPLACES = {
  US: { name: "Amazon US", domain: "https://www.amazon.com", postal: "10001 / New York", hint: "默认地区：New York, NY。" },
  CA: { name: "Amazon CA", domain: "https://www.amazon.ca", postal: "M5V 2T6 / Toronto", hint: "默认地区：Toronto。" },
  UK: { name: "Amazon UK", domain: "https://www.amazon.co.uk", postal: "SW1A 1AA / London", hint: "默认地区：London。" },
  DE: { name: "Amazon DE", domain: "https://www.amazon.de", postal: "10115 / Berlin", hint: "默认地区：Berlin。" },
  FR: { name: "Amazon FR", domain: "https://www.amazon.fr", postal: "75001 / Paris", hint: "默认地区：Paris。" },
  IT: { name: "Amazon IT", domain: "https://www.amazon.it", postal: "00118 / Rome", hint: "默认地区：Rome。" },
  ES: { name: "Amazon ES", domain: "https://www.amazon.es", postal: "28001 / Madrid", hint: "默认地区：Madrid。" },
  JP: { name: "Amazon JP", domain: "https://www.amazon.co.jp", postal: "100-0001 / Tokyo", hint: "默认地区：Tokyo。" },
  AU: { name: "Amazon AU", domain: "https://www.amazon.com.au", postal: "2000 / Sydney", hint: "默认地区：Sydney。" },
};

function showToast(message) {
  toast.textContent = message;
  toast.classList.add("show");
  clearTimeout(showToast.timer);
  showToast.timer = setTimeout(() => toast.classList.remove("show"), 3600);
}

function setBusy(isBusy) {
  runButton.disabled = isBusy;
  saveDailyButton.disabled = isBusy;
  testExcelButton.disabled = isBusy;
}

function activeOutputMode() {
  return new FormData(form).get("outputMode");
}

function getOwnerId() {
  let ownerId = localStorage.getItem(OWNER_KEY);
  if (!ownerId) {
    const randomPart = crypto.randomUUID
      ? crypto.randomUUID()
      : `${Date.now().toString(36)}-${Math.random().toString(36).slice(2)}`;
    ownerId = `kwt_${randomPart.replace(/[^A-Za-z0-9_-]/g, "")}`;
    localStorage.setItem(OWNER_KEY, ownerId);
  }
  return ownerId;
}

function captureFormData() {
  const data = new FormData(form);
  data.set("owner_id", getOwnerId());
  return data;
}

function syncDeliveryFields() {
  larkFields.hidden = activeOutputMode() === "excel";
}

function applyMarketplace(code) {
  const item = MARKETPLACES[code] || MARKETPLACES.US;
  marketplaceName.value = item.name;
  domain.value = item.domain;
  postalCode.value = item.postal;
  marketHint.textContent = item.hint;
}

function setProgress(percent, title, sub, log) {
  const pct = Math.max(0, Math.min(100, Number(percent)));
  progressPct.textContent = `${pct}%`;
  progressFill.style.width = `${pct}%`;
  progressTitle.textContent = title;
  progressSub.textContent = sub;
  if (log) {
    logBox.textContent = log;
    logBox.scrollTop = logBox.scrollHeight;
  }
}

async function refreshHistory() {
  const response = await fetch(`/api/history?owner_id=${encodeURIComponent(getOwnerId())}`);
  const data = await response.json();
  const records = data.records || [];
  historyBody.innerHTML = records
    .map(
      (record) => `
        <tr>
          <td>${escapeHtml(record.date || "")}</td>
          <td>${escapeHtml(record.asin || "")}</td>
          <td>${escapeHtml(record.keyword || "")}</td>
          <td>${escapeHtml(record.organic_position || "")}</td>
          <td>${escapeHtml(record.ad_position || "")}</td>
          <td>${escapeHtml(record.price || "")}</td>
          <td>${escapeHtml(record.estimated_sales || "")}</td>
          <td>${escapeHtml(record.product_rank || "")}</td>
          <td>${escapeHtml(record.rating || "")}</td>
          <td>${escapeHtml(record.review_count || "")}</td>
          <td>${record.product_url ? `<a href="${escapeAttribute(record.product_url)}" target="_blank" rel="noreferrer">打开</a>` : ""}</td>
        </tr>
      `,
    )
    .join("");
  recordCount.textContent = records.length;
  latestDate.textContent = records[0]?.date || "-";
}

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");
}

function escapeAttribute(value) {
  return escapeHtml(value).replaceAll("'", "&#39;");
}

function downloadBlob(blob, filename) {
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  link.click();
  URL.revokeObjectURL(url);
}

form.addEventListener("change", (event) => {
  if (event.target.name === "outputMode") syncDeliveryFields();
  if (event.target.id === "marketplaceSelect") applyMarketplace(event.target.value);
});

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  setBusy(true);
  resultLinks.innerHTML = "";
  setProgress(8, "提交任务中", "任务已提交，正在调用 Sorftime MCP。", "正在提交任务...");
  try {
    const response = await fetch("/api/capture", {
      method: "POST",
      body: captureFormData(),
    });
    const contentType = response.headers.get("Content-Type") || "";

    if (!response.ok && contentType.includes("application/json")) {
      const data = await response.json();
      throw new Error(data.error || "采集失败");
    }

    if (contentType.includes("spreadsheetml")) {
      setProgress(92, "正在生成 Excel", "结果已返回，正在下载文件。", "Excel 文件已生成。");
      const blob = await response.blob();
      downloadBlob(blob, `keyword-rank-results-${new Date().toISOString().slice(0, 10)}.xlsx`);
      resultLinks.innerHTML = `<span class="download">Excel 已下载</span>`;
      setProgress(100, "完成", "Excel 已生成并下载。", "任务完成。");
      showToast("Excel 已生成");
    } else {
      const data = await response.json();
      if (!data.ok) throw new Error(data.lark?.message || data.error || "写入飞书失败");
      const links = [];
      if (data.excel) links.push(`<a class="download" href="${escapeAttribute(data.excel)}">下载 Excel</a>`);
      if (data.lark) links.push(`<span class="download">飞书写入 ${data.records || 0} 行</span>`);
      resultLinks.innerHTML = links.join("");
      setProgress(100, "完成", `已处理 ${data.records || 0} 条记录。`, "任务完成。");
      showToast(`已处理：${data.records || 0} 条`);
    }
    await refreshHistory();
  } catch (error) {
    setProgress(12, "失败", error.message, error.stack || error.message);
    showToast(error.message);
  } finally {
    setBusy(false);
  }
});

testExcelButton.addEventListener("click", async () => {
  setBusy(true);
  setProgress(15, "测试导出中", "正在生成测试 Excel。", "正在请求测试导出...");
  try {
    const response = await fetch("/api/test-excel", { method: "POST" });
    if (!response.ok) throw new Error("测试导出失败");
    const blob = await response.blob();
    downloadBlob(blob, `keyword-rank-test-${new Date().toISOString().slice(0, 10)}.xlsx`);
    setProgress(100, "测试完成", "Excel 导出功能正常。", "测试 Excel 已下载。");
  } catch (error) {
    setProgress(12, "测试失败", error.message, error.stack || error.message);
  } finally {
    setBusy(false);
  }
});

saveDailyButton.addEventListener("click", async () => {
  setBusy(true);
  try {
    const response = await fetch("/api/daily", {
      method: "POST",
      body: captureFormData(),
    });
    const data = await response.json();
    if (!data.ok) throw new Error(data.error || "保存失败");
    showToast("每日任务已保存");
    setProgress(100, "每日任务已保存", "本地服务保持运行时会按时抓取。", "每日任务配置已保存。");
  } catch (error) {
    showToast(error.message);
  } finally {
    setBusy(false);
  }
});

document.querySelector("#refreshHistory").addEventListener("click", refreshHistory);

async function boot() {
  applyMarketplace(marketplaceSelect.value);
  syncDeliveryFields();
  await refreshHistory();
  sourceBadge.textContent = "输出自然位、广告位、价格、销量、排名、评分和评价数。";
}

boot();
