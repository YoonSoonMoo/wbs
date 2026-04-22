// ===== Gantt Chart =====
let ganttChart = null;
const ASSIGNEE_COLOR_COUNT = 12;
let assigneeColorMap = {};
let rawTimeline = [];
let currentViewMode = 'Week';

async function loadGantt() {
    try {
        const data = await API.get(`/api/wbs/${PROJECT_ID}/dashboard`);
        rawTimeline = data.timeline || [];

        if (rawTimeline.length === 0) {
            showGanttEmpty();
            return;
        }

        assigneeColorMap = buildAssigneeColorMap(rawTimeline);
        renderAssigneeLegend(assigneeColorMap);
        renderGanttChart();
    } catch (e) {
        showToast('Gantt 차트를 불러올 수 없습니다.', 'error');
    }
}

function renderGanttChart() {
    const includeDone = document.getElementById('ganttIncludeDone')?.checked;
    const chartEl = document.getElementById('gantt-chart');
    const emptyEl = document.getElementById('gantt-empty');

    const tasks = rawTimeline
        .filter(item => includeDone || (item.progress || 0) < 100)
        .map(item => {
            const done = (item.progress || 0) >= 100;
            const cls = [assigneeColorClass(item.assignee), done ? 'gantt-done' : '']
                .filter(Boolean).join(' ');
            return {
                id: String(item.id),
                name: buildGanttLabel(item),
                start: item.plan_start || item.actual_start,
                end: item.plan_end || item.actual_end || item.plan_start || item.actual_start,
                progress: item.progress || 0,
                dependencies: item.parent_id ? String(item.parent_id) : '',
                custom_class: cls,
            };
        })
        .filter(t => t.start);

    if (tasks.length === 0) {
        showGanttEmpty();
        return;
    }

    chartEl.style.display = '';
    emptyEl.style.display = 'none';
    chartEl.innerHTML = ''; // Frappe Gantt는 기존 SVG를 덮어쓰지 않으므로 수동 초기화

    ganttChart = new Gantt('#gantt-chart', tasks, {
        view_mode: currentViewMode,
        language: 'ko',
        on_date_change: async (task, start, end) => {
            try {
                await API.patch(`/api/wbs/items/${task.id}`, {
                    plan_start: formatGanttDate(start),
                    plan_end: formatGanttDate(end),
                });
                showToast('일정이 변경되었습니다.', 'success');
            } catch (e) {
                showToast('일정 변경 실패', 'error');
            }
        },
        on_progress_change: async (task, progress) => {
            try {
                await API.patch(`/api/wbs/items/${task.id}`, {
                    progress: Math.round(progress),
                });
            } catch (e) {
                showToast('진행률 변경 실패', 'error');
            }
        },
    });

    drawTodayLine();
}

function drawTodayLine() {
    if (!ganttChart) return;
    const svg = document.querySelector('#gantt-chart svg.gantt');
    if (!svg) return;

    const opts = ganttChart.options || {};
    const step = opts.step;                    // 컬럼당 시간 (시간 단위)
    const colWidth = opts.column_width;        // 컬럼당 픽셀
    const gs = ganttChart.gantt_start;
    if (!step || !colWidth || !gs) return;

    const startMs = new Date(gs).getTime();
    const nowMs = Date.now();
    const diffHours = (nowMs - startMs) / 3600000;
    const x = diffHours / step * colWidth;

    // SVG 영역 밖이면 숨김
    const svgWidth = parseFloat(svg.getAttribute('width')) || svg.getBoundingClientRect().width;
    if (x < 0 || x > svgWidth) return;

    const svgHeight = parseFloat(svg.getAttribute('height')) || svg.getBoundingClientRect().height;

    // 기존 선 제거 후 재생성 (재렌더/뷰모드 변경 대응)
    svg.querySelectorAll('.gantt-today-line,.gantt-today-label').forEach(el => el.remove());

    const NS = 'http://www.w3.org/2000/svg';
    const line = document.createElementNS(NS, 'line');
    line.setAttribute('class', 'gantt-today-line');
    line.setAttribute('x1', x);
    line.setAttribute('x2', x);
    line.setAttribute('y1', 0);
    line.setAttribute('y2', svgHeight);
    svg.appendChild(line);

    const label = document.createElementNS(NS, 'text');
    label.setAttribute('class', 'gantt-today-label');
    label.setAttribute('x', x + 4);
    label.setAttribute('y', 14);
    label.textContent = 'Today';
    svg.appendChild(label);
}

function showGanttEmpty() {
    document.getElementById('gantt-chart').style.display = 'none';
    document.getElementById('gantt-empty').style.display = 'block';
}

function toggleIncludeDone() {
    renderGanttChart();
}

function changeView(mode) {
    currentViewMode = mode;
    document.querySelectorAll('.gantt-view-btn').forEach(btn => {
        btn.classList.toggle('active', btn.dataset.mode === mode);
    });
    if (ganttChart) {
        ganttChart.change_view_mode(mode);
        drawTodayLine();
    }
}

function buildAssigneeColorMap(timeline) {
    // 정렬된 고유 담당자 리스트 → 안정적 인덱스 매핑
    const names = Array.from(new Set(
        timeline.map(t => (t.assignee || '').trim()).filter(Boolean)
    )).sort();
    const map = {};
    names.forEach((name, i) => {
        map[name] = i % ASSIGNEE_COLOR_COUNT;
    });
    return map;
}

function assigneeColorClass(assignee) {
    const name = (assignee || '').trim();
    if (!name) return 'gantt-assignee-none';
    const idx = assigneeColorMap[name];
    return idx === undefined ? 'gantt-assignee-none' : `gantt-assignee-${idx}`;
}

function renderAssigneeLegend(map) {
    const legend = document.getElementById('gantt-legend');
    if (!legend) return;
    const names = Object.keys(map);
    if (!names.length) { legend.innerHTML = ''; return; }
    legend.innerHTML = names.map(n =>
        `<span class="gantt-legend-item"><span class="gantt-legend-dot gantt-assignee-${map[n]}"></span>${n}</span>`
    ).join('');
}

function buildGanttLabel(item) {
    // 세부항목 우선, 없으면 서브태스크 / Task명으로 fallback. 15자 초과 시 '...' 처리.
    const base = item.detail || item.subtask || item.task_name || '';
    const truncated = base.length > 15 ? base.slice(0, 15) + '...' : base;
    const assignee = (item.assignee || '').trim();
    return assignee ? `${truncated} (${assignee})` : truncated;
}

function formatGanttDate(date) {
    const d = new Date(date);
    const y = d.getFullYear();
    const m = String(d.getMonth() + 1).padStart(2, '0');
    const day = String(d.getDate()).padStart(2, '0');
    return `${y}-${m}-${day}`;
}

document.addEventListener('DOMContentLoaded', loadGantt);
