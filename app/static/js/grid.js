// ===== WBS Grid (template 호환) =====
var COLUMNS = ['category','task_name','subtask','detail','assignee','plan_start','plan_end','actual_start','actual_end','effort','progress','status'];
var data = [];
var contextRowIdx = -1;
var sortCol = null;
var sortDir = 'asc';
var selectedRows = {};  // data index -> true
var lastClickedRowIdx = -1;
var aiFilterIds = null; // AI 필터 활성 시 표시할 항목 ID 배열 (null = 필터 없음)

// ===== Data Loading =====
async function loadItems() {
    try {
        var items = await API.get('/api/wbs/' + PROJECT_ID + '/items');
        data = items.map(function(item) {
            return {
                _id: item.id,
                category: item.category || '',
                task_name: item.task_name || '',
                subtask: item.subtask || '',
                detail: item.detail || '',
                assignee: item.assignee || '',
                plan_start: item.plan_start || '',
                plan_end: item.plan_end || '',
                actual_start: item.actual_start || '',
                actual_end: item.actual_end || '',
                effort: item.effort ? String(item.effort) : '',
                progress: item.progress != null ? String(item.progress) : '0',
                status: item.status || ''
            };
        });
        renderGrid();
    } catch (e) {
        showToast('데이터를 불러올 수 없습니다.', 'error');
    }
}

// ===== Rendering =====
function esc(s) {
    return (s || '').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
}

function renderGrid() {
    var tbody = document.getElementById('wbsBody');
    var sv = (document.getElementById('searchInput').value || '').toLowerCase();
    var fa = document.getElementById('filterAssignee').value;
    var showDone = document.getElementById('filterDone') && document.getElementById('filterDone').checked;
    var showMine = document.getElementById('filterMine') && document.getElementById('filterMine').checked;
    var filtered = [];

    for (var i = 0; i < data.length; i++) {
        var r = data[i]; r._idx = i;
        if (sv) {
            var found = false;
            for (var k in r) { if (String(r[k]).toLowerCase().indexOf(sv) >= 0) { found = true; break; } }
            if (!found) continue;
        }
        if (!showDone && (parseFloat(r.progress) || 0) >= 100) continue;
        if (showMine && (typeof USER_NAME !== 'undefined') && r.assignee !== USER_NAME) continue;
        if (fa && r.assignee !== fa) continue;
        if (aiFilterIds && aiFilterIds.indexOf(r._id) < 0) continue;
        filtered.push(r);
    }

    if (sortCol) {
        filtered.sort(function(a, b) {
            var va = a[sortCol] || '', vb = b[sortCol] || '';
            if (sortCol === 'progress' || sortCol === 'effort') { va = parseFloat(va) || 0; vb = parseFloat(vb) || 0; }
            return sortDir === 'asc' ? (va < vb ? -1 : va > vb ? 1 : 0) : (va > vb ? -1 : va < vb ? 1 : 0);
        });
    }

    var canEdit = (typeof USER_ROLE !== 'undefined' && USER_ROLE !== 'viewer');
    var ceAttr = canEdit ? ' contenteditable="true"' : '';
    var editClass = canEdit ? 'editable' : '';
    var canDrag = canEdit && !sortCol && !sv && !fa && !showMine;
    var todayDate = new Date(); todayDate.setHours(0,0,0,0);

    var h = '';
    for (var i = 0; i < filtered.length; i++) {
        var row = filtered[i];
        var p = parseFloat(row.progress) || 0;
        var pColor = p >= 100 ? 'var(--accent-green)' : p >= 50 ? 'var(--accent-blue)' : p > 0 ? 'var(--accent-yellow)' : '#d1d5db';
        var trClass = [];
        if (selectedRows[row._idx]) trClass.push('selected');
        if (p >= 100) trClass.push('completed');
        // Delayed: plan_end passed & not 100%
        var delayStyle = '';
        if (p < 100 && row.plan_end) {
            var pe = new Date(row.plan_end + 'T00:00:00');
            if (!isNaN(pe) && pe < todayDate) {
                trClass.push('delayed');
                var intensity = Math.round((100 - p) / 10) / 10; // 0%→1.0, 90%→0.1
                delayStyle = ' style="--delay:' + intensity + '"';
            }
        }
        var trClassAttr = trClass.length ? ' class="' + trClass.join(' ') + '"' : '';
        h += '<tr data-idx="' + row._idx + '"' + trClassAttr + delayStyle + (canEdit ? ' oncontextmenu="showContext(event,' + row._idx + ')"' : '') + '>';
        h += '<td class="row-num"' + (canDrag ? ' draggable="true"' : '') + ' onclick="handleRowSelect(event,' + row._idx + ')">' + (row._idx + 1) + '</td>';
        h += '<td class="' + editClass + '"' + ceAttr + ' data-col="category">' + esc(row.category) + '</td>';
        h += '<td class="' + editClass + '"' + ceAttr + ' data-col="task_name">' + esc(row.task_name) + '</td>';
        h += '<td class="' + editClass + '"' + ceAttr + ' data-col="subtask">' + esc(row.subtask) + '</td>';
        h += '<td class="expandable" data-col="detail">' + esc(row.detail) + '</td>';
        h += '<td class="' + editClass + ' cell-center"' + ceAttr + ' data-col="assignee">' + esc(row.assignee) + '</td>';
        h += '<td class="' + editClass + ' cell-date"' + ceAttr + ' data-col="plan_start">' + esc(shortDate(row.plan_start)) + '</td>';
        h += '<td class="' + editClass + ' cell-date"' + ceAttr + ' data-col="plan_end">' + esc(shortDate(row.plan_end)) + '</td>';
        h += '<td class="' + editClass + ' cell-date"' + ceAttr + ' data-col="actual_start">' + esc(shortDate(row.actual_start)) + '</td>';
        h += '<td class="' + editClass + ' cell-date"' + ceAttr + ' data-col="actual_end">' + esc(shortDate(row.actual_end)) + '</td>';
        h += '<td class="' + editClass + ' cell-num"' + ceAttr + ' data-col="effort">' + esc(row.effort) + '</td>';
        h += '<td class="cell-progress" data-col="progress" data-idx="' + row._idx + '"' + (canEdit ? ' onclick="editProgress(this,' + row._idx + ')"' : '') + '><div class="progress-bar-cell"><div class="progress-bar-bg"><div class="progress-bar-fill" style="width:' + p + '%;background:' + pColor + '"></div></div><span class="progress-val">' + p + '%</span></div></td>';
        h += '<td class="expandable cell-status" data-col="status">' + esc(row.status) + '</td>';
        h += '</tr>';
    }
    tbody.innerHTML = h;
    updateStats(filtered);
    updateAlerts();
    updateAssigneeFilter();
    updateSelectionUI();
    document.getElementById('footerRows').textContent = data.length;
}

// ===== Stats =====
function updateStats(f) {
    // 전체/완료/진행/지연은 필터와 무관하게 전체 data 기준으로 계산
    var today = new Date(); today.setHours(0,0,0,0);
    var done = 0, inProgress = 0, delayed = 0;
    for (var i = 0; i < data.length; i++) {
        var r = data[i];
        var pr = parseFloat(r.progress) || 0;
        if (pr >= 100) {
            done++;
        } else {
            // 지연 판단: plan_end < 오늘 && 미완료 (행 하이라이트 기준과 동일)
            var isDelayed = false;
            if (r.plan_end) {
                var pe = new Date(r.plan_end + (r.plan_end.indexOf('T') >= 0 ? '' : 'T00:00:00'));
                if (!isNaN(pe) && pe < today) isDelayed = true;
            }
            if (isDelayed) {
                delayed++;
            } else if (pr > 0) {
                inProgress++;
            }
        }
    }
    document.getElementById('statTotal').textContent = data.length;
    document.getElementById('statDone').textContent = done;
    document.getElementById('statProgress').textContent = inProgress;
    document.getElementById('statDelayed').textContent = delayed;
}

// ===== Alerts =====
function updateAlerts() {
    var today = new Date();
    var delayed = [];
    for (var i = 0; i < data.length; i++) {
        var r = data[i];
        if ((parseFloat(r.progress) || 0) >= 100 || !r.plan_end) continue;
        var ed;
        // YYYY-MM-DD format
        if (r.plan_end.indexOf('-') >= 0) {
            ed = new Date(r.plan_end);
        }
        // MM/DD format
        else if (r.plan_end.indexOf('/') >= 0) {
            var pts = r.plan_end.split('/');
            if (pts.length !== 2) continue;
            var m = parseInt(pts[0]) - 1, d = parseInt(pts[1]);
            if (isNaN(m) || isNaN(d)) continue;
            ed = new Date(today.getFullYear(), m, d);
        } else continue;

        if (ed < today) {
            var label = r.detail || r.subtask || r.task_name || '';
            if (label.length > 12) label = label.substring(0, 12) + '...';
            var assignee = r.assignee || '';
            if (assignee) label += '(' + assignee + ')';
            delayed.push({ label: label, days: Math.ceil((today - ed) / 864e5) });
        }
    }
    var sec = document.getElementById('alertSection');
    var con = document.getElementById('alertItems');
    document.getElementById('alertCount').textContent = delayed.length;
    if (!delayed.length) {
        sec.className = 'alert-section no-alerts';
        con.innerHTML = '<span class="alert-empty">지연된 업무가 없습니다 ✓</span>';
    } else {
        sec.className = 'alert-section';
        var ch = '';
        for (var i = 0; i < delayed.length; i++) {
            ch += '<span class="alert-chip"><span class="chip-task">' + esc(delayed[i].label) + '</span><span class="chip-days">+' + delayed[i].days + '일</span></span>';
        }
        con.innerHTML = ch;
    }
}

// ===== Assignee Filter =====
function updateAssigneeFilter() {
    var sel = document.getElementById('filterAssignee');
    var cur = sel.value;
    var m = {};
    for (var i = 0; i < data.length; i++) { if (data[i].assignee) m[data[i].assignee] = true; }
    var a = Object.keys(m).sort();
    sel.innerHTML = '<option value="">전체 담당자</option>';
    for (var i = 0; i < a.length; i++) {
        sel.innerHTML += '<option value="' + a[i] + '"' + (a[i] === cur ? ' selected' : '') + '>' + a[i] + '</option>';
    }
}

// ===== Row Selection =====
function handleRowSelect(e, idx) {
    e.stopPropagation();
    if (e.shiftKey && lastClickedRowIdx >= 0) {
        // Shift+click: range select
        var from = Math.min(lastClickedRowIdx, idx);
        var to = Math.max(lastClickedRowIdx, idx);
        for (var i = from; i <= to; i++) selectedRows[i] = true;
    } else if (e.ctrlKey || e.metaKey) {
        // Ctrl+click: toggle single
        if (selectedRows[idx]) delete selectedRows[idx];
        else selectedRows[idx] = true;
    } else {
        // Plain click: toggle single
        if (selectedRows[idx]) delete selectedRows[idx];
        else selectedRows[idx] = true;
    }
    lastClickedRowIdx = idx;
    applySelectionStyles();
    updateSelectionUI();
}

function applySelectionStyles() {
    var rows = document.querySelectorAll('#wbsBody tr');
    for (var i = 0; i < rows.length; i++) {
        var idx = parseInt(rows[i].dataset.idx);
        if (selectedRows[idx]) rows[i].classList.add('selected');
        else rows[i].classList.remove('selected');
    }
}

function selectAllRows() {
    var count = Object.keys(selectedRows).length;
    if (count > 0 && count === data.length) {
        // All selected -> deselect all
        selectedRows = {};
    } else {
        for (var i = 0; i < data.length; i++) selectedRows[i] = true;
    }
    applySelectionStyles();
    updateSelectionUI();
}

function clearSelection() {
    selectedRows = {};
    applySelectionStyles();
    updateSelectionUI();
}

function getSelectedCount() {
    return Object.keys(selectedRows).length;
}

function updateSelectionUI() {
    var count = getSelectedCount();
    var btn = document.getElementById('deleteSelectedBtn');
    if (btn) {
        if (count > 0) {
            btn.style.display = 'flex';
            btn.textContent = '✕ 선택 삭제 (' + count + ')';
        } else {
            btn.style.display = 'none';
        }
    }
    var info = document.getElementById('selectionInfo');
    if (info) {
        info.textContent = count > 0 ? count + '개 선택' : '';
    }
}

function deleteSelectedRows() {
    var indices = Object.keys(selectedRows).map(Number).sort(function(a, b) { return b - a; });
    if (indices.length === 0) return;
    if (!confirm(indices.length + '개 행을 삭제하시겠습니까?')) return;

    for (var i = 0; i < indices.length; i++) {
        var item = data[indices[i]];
        if (item && item._id) {
            API.delete('/api/wbs/items/' + item._id).catch(function() {});
        }
        data.splice(indices[i], 1);
    }
    selectedRows = {};
    lastClickedRowIdx = -1;
    renderGrid();
    showToast(indices.length + '개 행이 삭제되었습니다.', 'success');
}

function filterGrid() { renderGrid(); }

// ===== Date Parsing =====
var DATE_COLS = ['plan_start', 'plan_end', 'actual_start', 'actual_end'];

function parseDate(s) {
    if (!s) return '';
    s = s.trim();
    if (!s) return '';
    // Already yyyy-MM-dd
    if (/^\d{4}-\d{2}-\d{2}$/.test(s)) return s;

    var y, m, d, now = new Date();

    // yyyy/M/d or yyyy/MM/dd
    var r = s.match(/^(\d{4})[\/](\d{1,2})[\/](\d{1,2})$/);
    if (r) { y = parseInt(r[1]); m = parseInt(r[2]); d = parseInt(r[3]); return fmtDate(y, m, d); }

    // yy.M.d or yy.MM.dd (2-digit year)
    r = s.match(/^(\d{2})\.(\d{1,2})\.(\d{1,2})$/);
    if (r) { y = 2000 + parseInt(r[1]); m = parseInt(r[2]); d = parseInt(r[3]); return fmtDate(y, m, d); }

    // MM.dd (no year)
    r = s.match(/^(\d{1,2})\.(\d{1,2})$/);
    if (r) { y = now.getFullYear(); m = parseInt(r[1]); d = parseInt(r[2]); return fmtDate(y, m, d); }

    // M/d (no year, slash)
    r = s.match(/^(\d{1,2})[\/](\d{1,2})$/);
    if (r) { y = now.getFullYear(); m = parseInt(r[1]); d = parseInt(r[2]); return fmtDate(y, m, d); }

    // yyyy-M-d (not zero-padded)
    r = s.match(/^(\d{4})-(\d{1,2})-(\d{1,2})$/);
    if (r) { y = parseInt(r[1]); m = parseInt(r[2]); d = parseInt(r[3]); return fmtDate(y, m, d); }

    // yy년M월d일 or yyyy년M월d일
    r = s.match(/^(\d{2,4})년\s*(\d{1,2})월\s*(\d{1,2})일$/);
    if (r) { y = parseInt(r[1]); if (y < 100) y += 2000; m = parseInt(r[2]); d = parseInt(r[3]); return fmtDate(y, m, d); }

    // M월d일 (no year)
    r = s.match(/^(\d{1,2})월\s*(\d{1,2})일$/);
    if (r) { y = now.getFullYear(); m = parseInt(r[1]); d = parseInt(r[2]); return fmtDate(y, m, d); }

    return s; // unrecognized -> return as-is
}

function fmtDate(y, m, d) {
    return y + '-' + String(m).padStart(2, '0') + '-' + String(d).padStart(2, '0');
}

function shortDate(s) {
    if (!s) return '';
    var m = s.match(/^\d{4}(-\d{2}-\d{2})$/);
    return m ? s.substring(2) : s;
}

// ===== Cell Editing =====
var saveTimer = null;

document.addEventListener('focusin', function(e) {
    if (!e.target.classList.contains('editable')) return;
    var col = e.target.dataset.col;
    if (DATE_COLS.indexOf(col) < 0) return;
    var tr = e.target.closest('tr'); if (!tr) return;
    var idx = parseInt(tr.dataset.idx);
    if (data[idx]) e.target.textContent = data[idx][col] || '';
});

document.addEventListener('focusout', function(e) {
    if (!e.target.classList.contains('editable')) return;
    var tr = e.target.closest('tr'); if (!tr) return;
    var idx = parseInt(tr.dataset.idx), col = e.target.dataset.col;
    if (data[idx]) {
        var newVal = e.target.textContent.trim();
        // Date columns: normalize format
        if (DATE_COLS.indexOf(col) >= 0) newVal = parseDate(newVal);
        e.target.textContent = DATE_COLS.indexOf(col) >= 0 ? shortDate(newVal) : newVal;
        if (data[idx][col] !== newVal) {
            data[idx][col] = newVal;
            // Save to API
            saveField(data[idx]._id, col, newVal);
            if (col === 'progress') renderGrid();
        }
    }
});

document.addEventListener('keydown', function(e) {
    if (e.target.classList.contains('editable')) {
        if (e.key === 'Tab') {
            e.preventDefault();
            var n = e.shiftKey ? e.target.previousElementSibling : e.target.nextElementSibling;
            if (n && n.classList.contains('editable')) { n.focus(); window.getSelection().selectAllChildren(n); }
        }
        if (e.key === 'Enter') { e.preventDefault(); e.target.blur(); }
        return;
    }
    // Selection shortcuts (when not editing a cell)
    if (e.key === 'Escape') clearSelection();
    if (e.key === 'Delete' && getSelectedCount() > 0) deleteSelectedRows();
});

// ===== Paste in cell =====
document.addEventListener('paste', function(e) {
    var a = document.activeElement;
    if (a && a.classList.contains('editable')) {
        var t = (e.clipboardData || window.clipboardData).getData('text');
        if (t.indexOf('\t') >= 0 || (t.indexOf('\n') >= 0 && t.trim().split('\n').length > 1)) {
            e.preventDefault();
            pasteIntoGrid(t, a);
        }
    }
});

function pasteIntoGrid(text, cell) {
    var rows = text.split('\n');
    var rr = [];
    for (var i = 0; i < rows.length; i++) { if (rows[i].trim()) rr.push(rows[i]); }
    var tr = cell.closest('tr');
    var si = parseInt(tr.dataset.idx);
    var co = COLUMNS;
    var sci = co.indexOf(cell.dataset.col); if (sci < 0) sci = 0;
    for (var i = 0; i < rr.length; i++) {
        var cells = rr[i].split('\t');
        var di = si + i;
        while (di >= data.length) {
            data.push({ _id: null, category: '', task_name: '', subtask: '', detail: '', assignee: '', plan_start: '', plan_end: '', actual_start: '', actual_end: '', effort: '', progress: '0', status: '' });
        }
        for (var j = 0; j < cells.length; j++) {
            var ci = sci + j;
            if (ci < co.length) {
                var val = cells[j].trim();
                if (DATE_COLS.indexOf(co[ci]) >= 0) val = parseDate(val);
                data[di][co[ci]] = val;
            }
        }
    }
    saveBatch();
    renderGrid();
}

// ===== Sort =====
document.addEventListener('DOMContentLoaded', function() {
    document.querySelectorAll('th.sortable').forEach(function(th) {
        th.addEventListener('click', function() {
            var c = th.dataset.col;
            if (sortCol === c) sortDir = sortDir === 'asc' ? 'desc' : 'asc';
            else { sortCol = c; sortDir = 'asc'; }
            renderGrid();
        });
    });
    // # header click -> select all / deselect all
    var rownumTh = document.querySelector('th.col-rownum');
    if (rownumTh) rownumTh.addEventListener('click', selectAllRows);
});

// ===== Drag & Drop Row Reorder =====
var dragSrcIdx = -1;

document.addEventListener('dragstart', function(e) {
    if (!e.target.classList.contains('row-num')) return;
    var tr = e.target.closest('tr[data-idx]');
    if (!tr || !tr.closest('#wbsBody')) return;
    dragSrcIdx = parseInt(tr.dataset.idx);
    tr.classList.add('dragging');
    document.body.classList.add('is-dragging');
    e.dataTransfer.effectAllowed = 'move';
    e.dataTransfer.setData('text/plain', String(dragSrcIdx));
});

document.addEventListener('dragover', function(e) {
    if (dragSrcIdx < 0) return;
    var tr = e.target.closest('tr[data-idx]');
    if (!tr || !tr.closest('#wbsBody')) return;
    e.preventDefault();
    e.dataTransfer.dropEffect = 'move';
    // Clear previous indicators
    document.querySelectorAll('.drag-over-top,.drag-over-bottom').forEach(function(el) {
        el.classList.remove('drag-over-top', 'drag-over-bottom');
    });
    // Show drop position indicator
    var rect = tr.getBoundingClientRect();
    var mid = rect.top + rect.height / 2;
    if (e.clientY < mid) tr.classList.add('drag-over-top');
    else tr.classList.add('drag-over-bottom');
});

document.addEventListener('dragleave', function(e) {
    var tr = e.target.closest('tr[data-idx]');
    if (tr) tr.classList.remove('drag-over-top', 'drag-over-bottom');
});

document.addEventListener('drop', function(e) {
    if (dragSrcIdx < 0) return;
    e.preventDefault();
    var tr = e.target.closest('tr[data-idx]');
    if (!tr || !tr.closest('#wbsBody')) { cleanupDrag(); return; }

    var targetIdx = parseInt(tr.dataset.idx);
    if (targetIdx === dragSrcIdx) { cleanupDrag(); return; }

    // Determine insert position: above or below target
    var rect = tr.getBoundingClientRect();
    var insertBefore = e.clientY < rect.top + rect.height / 2;

    // Move in data array
    var item = data.splice(dragSrcIdx, 1)[0];
    var newIdx = targetIdx;
    if (dragSrcIdx < targetIdx) newIdx--;
    if (!insertBefore) newIdx++;
    data.splice(newIdx, 0, item);

    // Save new order to API
    saveSortOrder();
    selectedRows = {};
    cleanupDrag();
    renderGrid();
});

document.addEventListener('dragend', function() {
    cleanupDrag();
});

function cleanupDrag() {
    dragSrcIdx = -1;
    document.body.classList.remove('is-dragging');
    document.querySelectorAll('.dragging').forEach(function(el) { el.classList.remove('dragging'); });
    document.querySelectorAll('.drag-over-top,.drag-over-bottom').forEach(function(el) {
        el.classList.remove('drag-over-top', 'drag-over-bottom');
    });
}

function saveSortOrder() {
    var items = [];
    for (var i = 0; i < data.length; i++) {
        if (data[i]._id) {
            items.push({ id: data[i]._id, sort_order: i });
        }
    }
    if (items.length > 0) {
        API.post('/api/wbs/' + PROJECT_ID + '/items/batch', { items: items }).then(function() {
            document.getElementById('footerSaved').textContent = new Date().toLocaleTimeString('ko-KR');
        }).catch(function() {
            showToast('순서 저장 실패', 'error');
        });
    }
}

// ===== Row Operations =====
function addRow() {
    var newItem = { _id: null, category: '', task_name: '', subtask: '', detail: '', assignee: '', plan_start: '', plan_end: '', actual_start: '', actual_end: '', effort: '', progress: '0', status: '' };
    data.push(newItem);
    // Save to API
    API.post('/api/wbs/' + PROJECT_ID + '/items', { task_name: '' }).then(function(item) {
        newItem._id = item.id;
        renderGrid();
        var tb = document.getElementById('wbsBody');
        if (tb.lastElementChild) tb.lastElementChild.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
    }).catch(function() {
        showToast('행 추가 실패', 'error');
    });
    renderGrid();
}

function newRow() {
    return { _id: null, category: '', task_name: '', subtask: '', detail: '', assignee: '', plan_start: '', plan_end: '', actual_start: '', actual_end: '', effort: '', progress: '0', status: '' };
}

function showContext(e, idx) {
    e.preventDefault();
    if (typeof USER_ROLE !== 'undefined' && USER_ROLE === 'viewer') return;
    contextRowIdx = idx;
    var m = document.getElementById('contextMenu');
    m.style.left = e.clientX + 'px';
    m.style.top = e.clientY + 'px';
    // Show/hide multi-delete option
    var multiItem = document.getElementById('ctxDeleteSelected');
    var singleItem = document.getElementById('ctxDeleteSingle');
    var count = getSelectedCount();
    if (multiItem && singleItem) {
        if (count > 1) {
            multiItem.style.display = '';
            multiItem.textContent = '✕ 선택 행 삭제 (' + count + ')';
            singleItem.style.display = 'none';
        } else {
            multiItem.style.display = 'none';
            singleItem.style.display = '';
        }
    }
    m.classList.add('show');
}
document.addEventListener('click', function() { document.getElementById('contextMenu').classList.remove('show'); });

function insertRowAbove() {
    var nr = newRow();
    data.splice(contextRowIdx, 0, nr);
    API.post('/api/wbs/' + PROJECT_ID + '/items', { task_name: '', sort_order: contextRowIdx }).then(function(item) {
        nr._id = item.id;
        saveSortOrder();
    });
    renderGrid();
}

function insertRowBelow() {
    var nr = newRow();
    data.splice(contextRowIdx + 1, 0, nr);
    API.post('/api/wbs/' + PROJECT_ID + '/items', { task_name: '', sort_order: contextRowIdx + 1 }).then(function(item) {
        nr._id = item.id;
        saveSortOrder();
    });
    renderGrid();
}

function duplicateRow() {
    var o = {};
    var src = data[contextRowIdx];
    for (var k in src) o[k] = src[k];
    o._id = null;
    data.splice(contextRowIdx + 1, 0, o);
    var apiData = {};
    COLUMNS.forEach(function(c) { apiData[c] = o[c] || ''; });
    apiData.effort = parseFloat(apiData.effort) || 0;
    apiData.progress = parseInt(apiData.progress) || 0;
    API.post('/api/wbs/' + PROJECT_ID + '/items', apiData).then(function(item) {
        o._id = item.id;
        saveSortOrder();
    });
    renderGrid();
}

function deleteRow() {
    var item = data[contextRowIdx];
    if (item._id) {
        API.delete('/api/wbs/items/' + item._id).catch(function() {
            showToast('삭제 실패', 'error');
        });
    }
    data.splice(contextRowIdx, 1);
    renderGrid();
}

function confirmClear() {
    if (!confirm('모든 데이터를 초기화하시겠습니까?')) return;
    var promises = data.filter(function(r) { return r._id; }).map(function(r) {
        return API.delete('/api/wbs/items/' + r._id);
    });
    Promise.all(promises).then(function() {
        data = [];
        renderGrid();
        showToast('초기화되었습니다.', 'success');
    }).catch(function() {
        showToast('초기화 실패', 'error');
    });
}

// ===== API Save =====
var pendingSaves = {};

function saveField(id, col, value) {
    if (!id) return;
    var payload = {};
    if (col === 'effort') payload[col] = parseFloat(value) || 0;
    else if (col === 'progress') payload[col] = parseInt(value) || 0;
    else payload[col] = value;

    // Debounce per item
    if (pendingSaves[id]) clearTimeout(pendingSaves[id]);
    pendingSaves[id] = setTimeout(function() {
        API.patch('/api/wbs/items/' + id, payload).then(function() {
            document.getElementById('footerSaved').textContent = new Date().toLocaleTimeString('ko-KR');
        }).catch(function() {
            showToast('저장 실패', 'error');
        });
        delete pendingSaves[id];
    }, 300);
}

function saveBatch() {
    var items = [];
    for (var i = 0; i < data.length; i++) {
        var r = data[i];
        if (r._id) {
            var obj = { id: r._id };
            COLUMNS.forEach(function(c) { obj[c] = r[c] || ''; });
            obj.effort = parseFloat(obj.effort) || 0;
            obj.progress = parseInt(obj.progress) || 0;
            items.push(obj);
        } else {
            // Create new items
            var apiData = {};
            COLUMNS.forEach(function(c) { apiData[c] = r[c] || ''; });
            apiData.effort = parseFloat(apiData.effort) || 0;
            apiData.progress = parseInt(apiData.progress) || 0;
            (function(row) {
                API.post('/api/wbs/' + PROJECT_ID + '/items', apiData).then(function(item) {
                    row._id = item.id;
                });
            })(r);
        }
    }
    if (items.length > 0) {
        API.post('/api/wbs/' + PROJECT_ID + '/items/batch', { items: items }).then(function() {
            document.getElementById('footerSaved').textContent = new Date().toLocaleTimeString('ko-KR');
        }).catch(function() {
            showToast('일괄 저장 실패', 'error');
        });
    }
}

// ===== Paste Modal =====
function showPasteModal() {
    document.getElementById('pasteModal').classList.add('show');
    document.getElementById('pasteArea').value = '';
    setTimeout(function() { document.getElementById('pasteArea').focus(); }, 100);
}

function closePasteModal() {
    document.getElementById('pasteModal').classList.remove('show');
}

function importPaste() {
    var t = document.getElementById('pasteArea').value;
    if (!t.trim()) return;
    var rows = t.split('\n');
    var created = [];
    for (var i = 0; i < rows.length; i++) {
        if (!rows[i].trim()) continue;
        var cells = rows[i].split('\t');
        var obj = newRow();
        for (var j = 0; j < cells.length && j < COLUMNS.length; j++) {
            var val = cells[j].trim();
            if (DATE_COLS.indexOf(COLUMNS[j]) >= 0) val = parseDate(val);
            obj[COLUMNS[j]] = val;
        }
        data.push(obj);
        created.push(obj);
    }
    // Save all new rows to API
    created.forEach(function(row) {
        var apiData = {};
        COLUMNS.forEach(function(c) { apiData[c] = row[c] || ''; });
        apiData.effort = parseFloat(apiData.effort) || 0;
        apiData.progress = parseInt(apiData.progress) || 0;
        API.post('/api/wbs/' + PROJECT_ID + '/items', apiData).then(function(item) {
            row._id = item.id;
        });
    });
    closePasteModal();
    renderGrid();
    showToast(created.length + '개 행을 추가했습니다.', 'success');
}

// ===== Progress Inline Edit =====
function editProgress(td, idx) {
    if (td.querySelector('input')) return;
    var cur = parseInt(data[idx].progress) || 0;
    td.innerHTML = '<input type="number" min="0" max="100" value="' + cur + '" class="progress-input">';
    var input = td.querySelector('input');
    input.focus();
    input.select();

    function commit() {
        var val = Math.max(0, Math.min(100, parseInt(input.value) || 0));
        if (String(val) !== String(cur)) {
            data[idx].progress = String(val);
            saveField(data[idx]._id, 'progress', val);
        }
        renderGrid();
    }

    input.addEventListener('blur', commit);
    input.addEventListener('keydown', function(e) {
        if (e.key === 'Enter') { e.preventDefault(); input.blur(); }
        if (e.key === 'Escape') { e.preventDefault(); renderGrid(); }
    });
}

// ===== Expanded Editor (detail, status) =====
document.addEventListener('dblclick', function(e) {
    var td = e.target.closest('td.expandable');
    if (!td) return;
    e.preventDefault();
    window.getSelection().removeAllRanges();
    showExpandedEditor(td);
});

function showExpandedEditor(td) {
    var tr = td.closest('tr');
    if (!tr) return;
    var idx = parseInt(tr.dataset.idx);
    var col = td.dataset.col;
    if (!data[idx]) return;

    closeExpandedEditor();

    var canEdit = (typeof USER_ROLE !== 'undefined' && USER_ROLE !== 'viewer');
    var rect = td.getBoundingClientRect();
    var editorWidth = Math.max(rect.width, 320);

    // Overlay
    var overlay = document.createElement('div');
    overlay.id = 'expandedOverlay';
    overlay.style.cssText = 'position:fixed;top:0;left:0;right:0;bottom:0;z-index:999;';

    // Editor container
    var editor = document.createElement('div');
    editor.id = 'expandedEditor';
    var left = rect.left;
    if (left + editorWidth > window.innerWidth - 16) left = window.innerWidth - editorWidth - 16;
    if (left < 8) left = 8;
    var top = rect.bottom + 4;
    if (top + 220 > window.innerHeight) top = rect.top - 220;
    if (top < 8) top = 8;
    editor.style.cssText = 'position:fixed;z-index:1000;background:#fff;border:2px solid var(--accent-blue);border-radius:8px;box-shadow:0 8px 30px rgba(0,0,0,.18);padding:10px;width:' + editorWidth + 'px;';
    editor.style.left = left + 'px';
    editor.style.top = top + 'px';

    // Label
    var label = document.createElement('div');
    label.style.cssText = 'font-size:11px;font-weight:700;color:var(--text-secondary);margin-bottom:6px;';
    label.textContent = col === 'detail' ? '세부 항목' : '진행상태';
    editor.appendChild(label);

    // Textarea
    var textarea = document.createElement('textarea');
    textarea.style.cssText = 'width:100%;min-height:120px;max-height:300px;border:1px solid var(--border-color);border-radius:5px;font-family:var(--font-sans);font-size:12px;padding:8px;resize:vertical;line-height:1.7;outline:none;';
    textarea.value = data[idx][col] || '';
    if (!canEdit) textarea.readOnly = true;
    editor.appendChild(textarea);

    // Buttons
    var btnWrap = document.createElement('div');
    btnWrap.style.cssText = 'display:flex;justify-content:flex-end;gap:6px;margin-top:8px;';

    if (canEdit) {
        var cancelBtn = document.createElement('button');
        cancelBtn.className = 'btn';
        cancelBtn.textContent = '취소';
        cancelBtn.style.cssText = 'font-size:11px;height:26px;padding:2px 12px;';
        btnWrap.appendChild(cancelBtn);

        var saveBtn = document.createElement('button');
        saveBtn.className = 'btn btn-primary';
        saveBtn.textContent = '확인';
        saveBtn.style.cssText = 'font-size:11px;height:26px;padding:2px 12px;';
        btnWrap.appendChild(saveBtn);
    } else {
        var closeBtn = document.createElement('button');
        closeBtn.className = 'btn';
        closeBtn.textContent = '닫기';
        closeBtn.style.cssText = 'font-size:11px;height:26px;padding:2px 12px;';
        btnWrap.appendChild(closeBtn);
    }
    editor.appendChild(btnWrap);

    document.body.appendChild(overlay);
    document.body.appendChild(editor);
    textarea.focus();
    textarea.setSelectionRange(textarea.value.length, textarea.value.length);

    function close() {
        if (overlay.parentNode) overlay.remove();
        if (editor.parentNode) editor.remove();
    }

    function save() {
        var newVal = textarea.value.trim();
        if (data[idx][col] !== newVal) {
            data[idx][col] = newVal;
            saveField(data[idx]._id, col, newVal);
            renderGrid();
        }
        close();
    }

    overlay.addEventListener('click', function() { canEdit ? save() : close(); });
    textarea.addEventListener('keydown', function(e) {
        if (e.key === 'Escape') { e.stopPropagation(); close(); }
    });

    if (canEdit) {
        cancelBtn.addEventListener('click', function(e) { e.stopPropagation(); close(); });
        saveBtn.addEventListener('click', function(e) { e.stopPropagation(); save(); });
    } else {
        closeBtn.addEventListener('click', function(e) { e.stopPropagation(); close(); });
    }
}

function closeExpandedEditor() {
    var o = document.getElementById('expandedOverlay');
    var e = document.getElementById('expandedEditor');
    if (o) o.remove();
    if (e) e.remove();
}

// ===== Export =====
function exportCSV() {
    window.open('/api/io/' + PROJECT_ID + '/export/csv', '_blank');
}

function exportExcel() {
    window.open('/api/io/' + PROJECT_ID + '/export/excel', '_blank');
}

// ===== AI Assistant =====
function sendAiQuery() {
    var input = document.getElementById('aiInput');
    var query = input.value.trim();
    if (!query) return;

    var bar = document.getElementById('aiBar');
    var result = document.getElementById('aiResult');
    var btn = document.getElementById('aiSendBtn');

    bar.classList.add('loading');
    btn.disabled = true;
    btn.textContent = '처리중...';
    result.style.display = 'none';

    API.post('/api/wbs/' + PROJECT_ID + '/ai', { query: query })
        .then(function(res) {
            bar.classList.remove('loading');
            btn.disabled = false;
            btn.textContent = '전송';
            result.style.display = 'block';

            if (!res.success) {
                result.innerHTML = '<span class="ai-close" onclick="closeAiResult()">&times;</span>'
                    + '<div class="ai-error">' + esc(res.message) + '</div>';
                return;
            }

            var html = '<span class="ai-close" onclick="closeAiResult()">&times;</span>';

            if (res.action === 'query' && res.data && res.data.items) {
                var items = res.data.items;
                if (items.length === 0) {
                    aiFilterIds = null;
                    html += '<div class="ai-msg">' + esc(res.message) + '</div>';
                    html += '<div style="color:var(--text-muted);padding:8px 0;">조건에 맞는 항목이 없습니다.</div>';
                } else {
                    // 그리드에 AI 필터 적용
                    aiFilterIds = items.map(function(it) { return it.id; });
                    renderGrid();

                    // 메시지 + 인라인 통계
                    var sm = res.data.summary;
                    html += '<div class="ai-msg">' + esc(res.message) + '</div>';
                    if (sm) {
                        html += '<div class="ai-summary-bar">';
                        html += '<span><strong>' + sm.count + '</strong>건</span>';
                        html += '<span>공수 <strong>' + sm.total_effort + '</strong></span>';
                        html += '<span>진행률 <strong>' + sm.avg_progress + '%</strong></span>';
                        html += '</div>';
                    }

                    // AI 분석 코멘트 (있으면)
                    if (res.insight) {
                        html += '<div class="ai-insight">💡 ' + esc(res.insight).replace(/\n/g, '<br>') + '</div>';
                    }

                    // 일정 지연 칩 (지연 항목만)
                    var delayItems = items.filter(function(it) { return (it.end_gap_days || 0) > 0; });
                    if (delayItems.length > 0) {
                        html += '<div class="ai-schedule-summary">';
                        for (var i = 0; i < delayItems.length; i++) {
                            var it = delayItems[i];
                            html += '<span class="ai-gap-chip gap-delay">#' + it._row_number + ' ' + esc(it.task_name || '') + ' <strong>+' + it.end_gap_days + '일</strong></span>';
                        }
                        html += '</div>';
                    }

                    html += '<button class="btn ai-clear-btn" onclick="clearAiFilter()">필터 해제</button>';
                }
            } else if (res.action === 'add' || res.action === 'delete' || res.action === 'update') {
                aiFilterIds = null;
                loadItems();
                html += '<div class="ai-msg">' + esc(res.message) + '</div>';
            } else {
                html += '<div class="ai-msg">' + esc(res.message) + '</div>';
            }

            result.innerHTML = html;
        })
        .catch(function(e) {
            bar.classList.remove('loading');
            btn.disabled = false;
            btn.textContent = '전송';
            result.style.display = 'block';
            result.innerHTML = '<span class="ai-close" onclick="closeAiResult()">&times;</span>'
                + '<div class="ai-error">요청 처리 중 오류가 발생했습니다.</div>';
        });
}

function clearAiFilter() {
    aiFilterIds = null;
    renderGrid();
    closeAiResult();
}

function closeAiResult() {
    document.getElementById('aiResult').style.display = 'none';
}

// ===== Init =====
document.addEventListener('DOMContentLoaded', loadItems);
