// ===== Dashboard =====
var editingProjectId = null;
var currentEditRole = null;   // 현재 편집 중인 프로젝트에서 내 역할 (admin/pm)
var availableUsers = [];

async function loadProjects() {
    try {
        var projects = await API.get('/api/projects');
        renderProjects(projects);
    } catch (e) {
        document.getElementById('project-list').innerHTML =
            '<div class="empty-state"><p>프로젝트를 불러올 수 없습니다.</p></div>';
    }
}

async function renderProjects(projects) {
    var container = document.getElementById('project-list');
    var isAdmin = (typeof USER_ROLE !== 'undefined' && USER_ROLE === 'admin');

    if (projects.length === 0) {
        var emptyHtml = '<div class="empty-state"><p>아직 프로젝트가 없습니다.</p>';
        if (isAdmin) emptyHtml += '<button class="btn btn-primary" onclick="showCreateProjectModal()">첫 프로젝트 만들기</button>';
        emptyHtml += '</div>';
        container.innerHTML = emptyHtml;
        return;
    }

    var html = '';
    for (var i = 0; i < projects.length; i++) {
        var project = projects[i];
        var stats = { total: 0, completed: 0, in_progress: 0, delayed: 0, avg_progress: 0 };
        try {
            stats = await API.get('/api/wbs/' + project.id + '/stats');
        } catch (e) { /* ignore */ }

        html += '<div class="project-card" onclick="location.href=\'/project/' + project.id + '/wbs\'">';
        html += '<h3>' + escapeHtml(project.name) + '</h3>';
        html += '<div class="desc">' + escapeHtml(project.description || '설명 없음') + '</div>';
        html += '<div class="meta"><span>' + (project.start_date || '-') + ' ~ ' + (project.end_date || '-') + '</span></div>';
        html += '<div class="progress-bar"><div class="progress-bar-fill" style="width:' + stats.avg_progress + '%"></div></div>';
        html += '<div class="stats">';
        html += '<div class="stat-item"><div class="stat-value">' + stats.total + '</div><div class="stat-label">전체</div></div>';
        html += '<div class="stat-item"><div class="stat-value">' + stats.completed + '</div><div class="stat-label">완료</div></div>';
        html += '<div class="stat-item"><div class="stat-value">' + stats.in_progress + '</div><div class="stat-label">진행중</div></div>';
        html += '<div class="stat-item"><div class="stat-value" style="color:' + (stats.delayed > 0 ? 'var(--danger)' : '') + '">' + stats.delayed + '</div><div class="stat-label">지연</div></div>';
        html += '<div class="stat-item"><div class="stat-value">' + stats.avg_progress + '%</div><div class="stat-label">진행률</div></div>';
        html += '</div>';

        var myRole = project.my_role || (isAdmin ? 'admin' : '');
        var canManage = (myRole === 'admin' || myRole === 'pm');
        if (canManage) {
            var histOn = !!project.history_enabled;
            var histCls = histOn ? 'btn btn-hist-toggle on' : 'btn btn-hist-toggle';
            var histLabel = histOn ? '이력: ON' : '이력: OFF';
            html += '<div class="project-actions" onclick="event.stopPropagation()">';
            html += '<button class="btn" onclick="editProject(' + project.id + ', \'' + myRole + '\')">수정</button>';
            html += '<button class="btn" style="color:var(--danger)" onclick="clearProjectData(' + project.id + ', \'' + escapeHtml(project.name).replace(/'/g, "\\'") + '\')">데이터 초기화</button>';
            html += '<button class="btn" style="color:var(--danger)" onclick="deleteProject(' + project.id + ', \'' + escapeHtml(project.name).replace(/'/g, "\\'") + '\')">삭제</button>';
            html += '<button class="' + histCls + '" data-pid="' + project.id + '" onclick="toggleProjectHistory(' + project.id + ', ' + (histOn ? 0 : 1) + ', this)" title="변경 이력 기록 ON/OFF">' + histLabel + '</button>';
            html += '</div>';
        }

        html += '</div>';
    }
    container.innerHTML = html;
}

// ===== Modal =====
async function showCreateProjectModal() {
    editingProjectId = null;
    currentEditRole = 'admin';   // 새 프로젝트는 admin만 생성
    document.getElementById('modal-title').textContent = '새 프로젝트';
    document.getElementById('project-form').reset();
    document.getElementById('project-id').value = '';
    clearMemberList();
    await loadAvailableUsers();
    document.getElementById('project-modal').style.display = 'flex';
}

async function editProject(id, myRole) {
    try {
        var project = await API.get('/api/projects/' + id);
        editingProjectId = id;
        currentEditRole = myRole || 'admin';
        document.getElementById('modal-title').textContent = '프로젝트 수정';
        document.getElementById('project-id').value = id;
        document.getElementById('project-name').value = project.name;
        document.getElementById('project-desc').value = project.description || '';
        document.getElementById('project-notice').value = project.notice || '';
        document.getElementById('project-start').value = project.start_date || '';
        document.getElementById('project-end').value = project.end_date || '';

        var notifyEnabled = document.getElementById('project-task-notify-enabled');
        var notifyTime = document.getElementById('project-task-notify-time');
        if (notifyEnabled) notifyEnabled.checked = !!project.task_notify_enabled;
        if (notifyTime) notifyTime.value = (project.task_notify_time || '09:00').slice(0, 5);

        clearMemberList();
        await loadAvailableUsers();
        // 기존 멤버 로드
        var members = await API.get('/api/projects/' + id + '/members');
        for (var i = 0; i < members.length; i++) {
            addMemberRow(members[i].id, members[i].role);
        }

        document.getElementById('project-modal').style.display = 'flex';
    } catch (e) {
        showToast('프로젝트를 불러올 수 없습니다.', 'error');
    }
}

function closeModal() {
    document.getElementById('project-modal').style.display = 'none';
}

async function handleProjectSubmit(e) {
    e.preventDefault();
    var data = {
        name: document.getElementById('project-name').value,
        description: document.getElementById('project-desc').value,
        notice: document.getElementById('project-notice').value,
        start_date: document.getElementById('project-start').value || null,
        end_date: document.getElementById('project-end').value || null,
    };

    // 멤버/역할 지정: admin 또는 해당 프로젝트 PM
    if (currentEditRole === 'admin' || currentEditRole === 'pm') {
        data.members = collectMembers();
    }
    // 태스크 갱신 알림: admin 전용 (입력 요소가 렌더된 경우에만 전송)
    var notifyEnabled = document.getElementById('project-task-notify-enabled');
    var notifyTime = document.getElementById('project-task-notify-time');
    if (notifyEnabled) data.task_notify_enabled = notifyEnabled.checked ? 1 : 0;
    if (notifyTime) data.task_notify_time = notifyTime.value || '09:00';

    try {
        if (editingProjectId) {
            await API.put('/api/projects/' + editingProjectId, data);
            showToast('프로젝트가 수정되었습니다.', 'success');
        } else {
            await API.post('/api/projects', data);
            showToast('프로젝트가 생성되었습니다.', 'success');
        }
        closeModal();
        loadProjects();
    } catch (e) {
        showToast('저장에 실패했습니다.', 'error');
    }
}

async function sendTaskUpdateNow() {
    if (!editingProjectId) {
        showToast('먼저 프로젝트를 저장한 뒤 발송할 수 있습니다.', 'error');
        return;
    }
    if (!confirm('이번주 할당 태스크를 담당자에게 지금 메일로 발송하시겠습니까?')) return;

    var btn = document.querySelector('.task-notify-sendnow');
    if (btn) { btn.disabled = true; btn.textContent = '발송 중...'; }
    try {
        var res = await API.post('/api/wbs/' + editingProjectId + '/send-task-update-mail', {});
        var sent = (res && res.sent) || 0;
        var total = (res && res.total) || 0;
        if (total === 0) {
            showToast('이번주 할당된 태스크가 없습니다.', 'info');
        } else if (sent === total) {
            showToast(sent + '명에게 발송 완료', 'success');
        } else {
            // 일부 실패 — 사유 함께 안내
            var fails = (res.results || []).filter(function (r) { return !r.success; })
                .map(function (r) { return r.assignee + '(' + (r.message || '실패') + ')'; });
            showToast('발송 ' + sent + '/' + total + ' 완료. 실패: ' + fails.join(', '), 'error');
        }
    } catch (e) {
        showToast('발송에 실패했습니다.', 'error');
    } finally {
        if (btn) { btn.disabled = false; btn.textContent = '즉시발송'; }
    }
}

async function deleteProject(id, name) {
    if (!confirm('"' + name + '" 프로젝트를 삭제하시겠습니까?\n모든 WBS 항목도 함께 삭제됩니다.')) return;
    try {
        await API.delete('/api/projects/' + id);
        showToast('프로젝트가 삭제되었습니다.', 'success');
        loadProjects();
    } catch (e) {
        showToast('삭제에 실패했습니다.', 'error');
    }
}

// ===== History Toggle =====
async function toggleProjectHistory(projectId, nextEnabled, btn) {
    if (btn) btn.disabled = true;
    try {
        var res = await API.patch('/api/projects/' + projectId + '/history-flag', { enabled: !!nextEnabled });
        var on = !!(res && res.history_enabled);
        if (btn) {
            btn.className = on ? 'btn btn-hist-toggle on' : 'btn btn-hist-toggle';
            btn.textContent = on ? '이력: ON' : '이력: OFF';
            btn.setAttribute('onclick', 'toggleProjectHistory(' + projectId + ', ' + (on ? 0 : 1) + ', this)');
        }
        showToast(on ? '이력 관리 활성화' : '이력 관리 비활성화', 'success');
    } catch (e) {
        showToast('변경 실패', 'error');
    } finally {
        if (btn) btn.disabled = false;
    }
}

// ===== Data Reset =====
async function clearProjectData(id, name) {
    if (!confirm('"' + name + '" 프로젝트의 WBS 데이터를 모두 초기화하시겠습니까?\n이 작업은 되돌릴 수 없습니다.')) return;
    try {
        await API.delete('/api/wbs/' + id + '/items');
        showToast('WBS 데이터가 초기화되었습니다.', 'success');
        loadProjects();
    } catch (e) {
        showToast('초기화에 실패했습니다.', 'error');
    }
}

// ===== Member Assignment =====
async function loadAvailableUsers() {
    try {
        availableUsers = await API.get('/api/projects/users');
    } catch (e) {
        availableUsers = [];
    }
}

function clearMemberList() {
    var list = document.getElementById('member-list');
    if (list) list.innerHTML = '';
}

var MEMBER_ROLES = [['pm', 'PM'], ['pl', 'PL'], ['developer', '개발자'], ['viewer', '뷰어']];

function addMemberRow(selectedUserId, selectedRole) {
    var list = document.getElementById('member-list');
    if (!list) return;

    if (selectedUserId) {
        var found = false;
        for (var k = 0; k < availableUsers.length; k++) {
            if (availableUsers[k].id === selectedUserId) { found = true; break; }
        }
        if (!found) return;
    }

    var row = document.createElement('div');
    row.className = 'member-row';

    var userOptions = '';
    for (var i = 0; i < availableUsers.length; i++) {
        var u = availableUsers[i];
        var sel = (selectedUserId && u.id === selectedUserId) ? ' selected' : '';
        userOptions += '<option value="' + u.id + '"' + sel + '>' + escapeHtml(u.name) + ' (' + escapeHtml(u.email) + ')</option>';
    }

    var role = selectedRole || 'developer';
    var roleOptions = '';
    for (var r = 0; r < MEMBER_ROLES.length; r++) {
        var rsel = (MEMBER_ROLES[r][0] === role) ? ' selected' : '';
        roleOptions += '<option value="' + MEMBER_ROLES[r][0] + '"' + rsel + '>' + MEMBER_ROLES[r][1] + '</option>';
    }

    // 프로젝트별 역할(PM/PL/개발자/뷰어)을 멤버 행에서 지정 (admin 전용 화면)
    row.innerHTML = '<select class="member-user" style="flex:1;">' + userOptions + '</select>' +
        '<select class="member-role" style="width:90px;">' + roleOptions + '</select>' +
        '<button type="button" class="btn-remove" onclick="this.parentElement.remove()">&times;</button>';

    list.appendChild(row);
}

function collectMembers() {
    var rows = document.querySelectorAll('.member-row');
    var members = [];
    for (var i = 0; i < rows.length; i++) {
        var userId = rows[i].querySelector('.member-user');
        var roleSel = rows[i].querySelector('.member-role');
        if (userId) {
            members.push({ user_id: parseInt(userId.value), role: roleSel ? roleSel.value : 'developer' });
        }
    }
    return members;
}

// ===== Utility =====
function escapeHtml(str) {
    var div = document.createElement('div');
    div.textContent = str;
    return div.innerHTML;
}

// ===== User Management (admin only) =====
async function openUserMgmtModal() {
    document.getElementById('user-mgmt-modal').style.display = 'flex';
    await loadUserMgmtList();
}

function closeUserMgmtModal() {
    document.getElementById('user-mgmt-modal').style.display = 'none';
}

async function loadUserMgmtList() {
    var tbody = document.getElementById('user-mgmt-tbody');
    var sub = document.getElementById('user-mgmt-sub');
    try {
        var users = await API.get('/api/users');
        if (users.length === 0) {
            tbody.innerHTML = '<tr><td colspan="5" class="user-mgmt-empty">등록된 유저가 없습니다.</td></tr>';
            if (sub) sub.textContent = '등록된 유저가 없습니다.';
            return;
        }
        var activeCnt = users.filter(function(u) { return u.is_active; }).length;
        if (sub) sub.textContent = '전체 ' + users.length + '명 · 활성 ' + activeCnt + '명 · 비활성 ' + (users.length - activeCnt) + '명';

        var h = '';
        for (var i = 0; i < users.length; i++) {
            var u = users[i];
            var isSelf = (u.id === CURRENT_USER_ID);
            // 전역 역할은 관리자/일반 2단계 (업무 권한 PM/PL/개발자/뷰어는 프로젝트별로 지정)
            var isAdminRole = (u.role === 'admin');
            var roleOpts = '<option value="admin"' + (isAdminRole ? ' selected' : '') + '>관리자</option>'
                + '<option value="developer"' + (isAdminRole ? '' : ' selected') + '>일반 사용자</option>';
            var activeBadge = u.is_active
                ? '<span class="user-badge user-badge-active">활성</span>'
                : '<span class="user-badge user-badge-inactive">비활성</span>';
            var toggleLabel = u.is_active ? '비활성화' : '활성화';
            var toggleClass = u.is_active ? 'btn danger' : 'btn';
            var toggleDisabled = (isSelf && u.is_active) ? ' disabled title="본인은 비활성화 불가"' : '';
            var emailAttr = u.email.replace(/'/g, "\\'");
            h += '<tr data-uid="' + u.id + '">'
                + '<td class="user-mgmt-name">' + escapeHtml(u.name) + (isSelf ? '<span class="self-tag">나</span>' : '') + '</td>'
                + '<td class="user-mgmt-email">' + escapeHtml(u.email) + '</td>'
                + '<td><select class="user-role-sel" onchange="changeUserRole(' + u.id + ', this.value)">' + roleOpts + '</select></td>'
                + '<td>' + activeBadge + '</td>'
                + '<td><div class="user-action-btns">'
                + '<button class="btn" onclick="resetUserPw(' + u.id + ', \'' + emailAttr + '\')">PW 리셋</button>'
                + '<button class="btn" onclick="issueApiToken(' + u.id + ', \'' + emailAttr + '\')">토큰 발급</button>'
                + '<button class="' + toggleClass + '" onclick="toggleUserActive(' + u.id + ', ' + (u.is_active ? 0 : 1) + ')"' + toggleDisabled + '>' + toggleLabel + '</button>'
                + '</div></td>'
                + '</tr>';
        }
        tbody.innerHTML = h;
    } catch (e) {
        tbody.innerHTML = '<tr><td colspan="5" class="user-mgmt-empty" style="color:#e84040;">유저 목록을 불러올 수 없습니다.</td></tr>';
    }
}

async function changeUserRole(userId, role) {
    try {
        await API.put('/api/users/' + userId + '/role', { role: role });
        showToast('권한이 변경되었습니다.', 'success');
    } catch (e) {
        showToast('권한 변경 실패', 'error');
        loadUserMgmtList();
    }
}

async function resetUserPw(userId, email) {
    if (!confirm(email + ' 계정으로 임시 비밀번호를 전송하시겠습니까?')) return;
    try {
        await API.post('/api/users/' + userId + '/reset-password', {});
        showToast('임시 비밀번호가 이메일로 전송되었습니다.', 'success');
    } catch (e) {
        showToast('비밀번호 초기화 실패', 'error');
    }
}

async function issueApiToken(userId, email) {
    if (!confirm(email + ' 계정의 API 토큰을 발급하시겠습니까?\n기존 토큰이 있으면 즉시 무효화되며, 새 토큰은 이메일로 전송됩니다.')) return;
    try {
        await API.post('/api/users/' + userId + '/api-token', {});
        showToast('API 토큰이 이메일로 전송되었습니다.', 'success');
    } catch (e) {
        showToast('토큰 발급 실패', 'error');
    }
}

async function toggleUserActive(userId, nextActive) {
    var msg = nextActive ? '이 유저를 활성화할까요?' : '이 유저를 비활성화할까요? 로그인할 수 없게 됩니다.';
    if (!confirm(msg)) return;
    try {
        await API.put('/api/users/' + userId + '/active', { is_active: nextActive });
        showToast(nextActive ? '활성화 완료' : '비활성화 완료', 'success');
        loadUserMgmtList();
    } catch (e) {
        showToast('상태 변경 실패', 'error');
    }
}

// ===== 백업/복원 (admin only) =====
function openBackupModal() {
    document.getElementById('backup-modal').style.display = 'flex';
}

function closeBackupModal() {
    document.getElementById('backup-modal').style.display = 'none';
}

function downloadBackup() {
    window.location.href = '/api/admin/backup';
}

async function restoreBackup() {
    var input = document.getElementById('restore-file');
    if (!input.files || !input.files[0]) {
        showToast('복원할 백업 파일을 선택하세요.', 'error');
        return;
    }
    if (!confirm('현재 모든 데이터를 업로드한 백업으로 덮어씁니다.\n이 작업은 되돌릴 수 없습니다. 계속하시겠습니까?')) return;

    var fd = new FormData();
    fd.append('file', input.files[0]);
    try {
        var res = await fetch('/api/admin/restore', { method: 'POST', body: fd });
        var result = await res.json();
        if (!res.ok) {
            showToast(result.error || '복원에 실패했습니다.', 'error');
            return;
        }
        showToast('복원 완료. 새로고침합니다.', 'success');
        setTimeout(function() { location.reload(); }, 1000);
    } catch (e) {
        showToast('복원 중 오류가 발생했습니다.', 'error');
    }
}

// ===== Init =====
document.addEventListener('DOMContentLoaded', loadProjects);
