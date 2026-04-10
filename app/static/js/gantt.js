// ===== Gantt Chart =====
let ganttChart = null;

async function loadGantt() {
    try {
        const data = await API.get(`/api/wbs/${PROJECT_ID}/dashboard`);
        const timeline = data.timeline;

        if (!timeline || timeline.length === 0) {
            document.getElementById('gantt-chart').style.display = 'none';
            document.getElementById('gantt-empty').style.display = 'block';
            return;
        }

        const tasks = timeline.map(item => ({
            id: String(item.id),
            name: `${item.wbs_code} ${item.task_name}`,
            start: item.plan_start || item.actual_start,
            end: item.plan_end || item.actual_end || item.plan_start || item.actual_start,
            progress: item.progress || 0,
            dependencies: item.parent_id ? String(item.parent_id) : '',
        })).filter(t => t.start);

        if (tasks.length === 0) {
            document.getElementById('gantt-chart').style.display = 'none';
            document.getElementById('gantt-empty').style.display = 'block';
            return;
        }

        ganttChart = new Gantt('#gantt-chart', tasks, {
            view_mode: 'Week',
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
    } catch (e) {
        showToast('Gantt 차트를 불러올 수 없습니다.', 'error');
    }
}

function changeView(mode) {
    if (ganttChart) {
        ganttChart.change_view_mode(mode);
        document.querySelectorAll('.gantt-view-btn').forEach(btn => {
            btn.classList.toggle('active', btn.dataset.mode === mode);
        });
    }
}

function formatGanttDate(date) {
    const d = new Date(date);
    const y = d.getFullYear();
    const m = String(d.getMonth() + 1).padStart(2, '0');
    const day = String(d.getDate()).padStart(2, '0');
    return `${y}-${m}-${day}`;
}

document.addEventListener('DOMContentLoaded', loadGantt);
