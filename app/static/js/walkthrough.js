// ===== WBS Grid Walkthrough (경량, 외부 의존성 없음) =====
(function() {
    const STORAGE_KEY = 'wbs_tour_done_' + (typeof USER_NAME !== 'undefined' ? USER_NAME : 'anon');

    const STEPS = [
        {
            selector: '.top-bar-actions',
            title: '상단 기능 버튼',
            text:
                '화면 우측 상단에는 WBS 관리의 핵심 진입점들이 좌→우 순서로 배치되어 있습니다. 각 버튼의 역할을 먼저 익히면 이후 단계가 한결 수월합니다.' +
                '<ul class="tour-list">' +
                '<li><b>📋 대시보드</b> — 프로젝트 목록으로 돌아갑니다.</li>' +
                '<li><b>📊 통계</b> — 주간 진척률, 담당자별 현황, 진척 추이 라인 차트를 모달로 확인합니다.</li>' +
                '<li><b>📥 CSV / 📥 Excel</b> — 현재 WBS 전체를 파일로 내려받습니다. Excel은 헤더 서식 포함.</li>' +
                '<li><b>📋 Excel 붙여넣기</b> — Excel에서 복사한 탭 구분 데이터를 모달에 붙여넣어 일괄 등록합니다.</li>' +
                '<li><b>📊 Gantt</b> — 일정을 담당자별 색상의 타임라인 차트로 시각화합니다 (오늘 기준 세로선, 완료 태스크 회색 처리).</li>' +
                '<li><b>❓ 가이드</b> — 지금 보고 있는 튜토리얼을 언제든 다시 실행합니다. (가장 오른쪽)</li>' +
                '</ul>',
            placement: 'bottom',
        },
        {
            selector: '#alertSection',
            title: '오늘의 알림',
            text: '계획 완료일이 지난 미완료 태스크가 자동으로 여기에 표시됩니다. 관리자는 담당자에게 메일 일괄 발송도 가능합니다.',
            placement: 'bottom',
        },
        {
            selector: '#aiBar',
            title: 'AI Assistant',
            text: '자연어로 "지연된 태스크 보여줘"처럼 말하면 그리드에 바로 반영됩니다. 조회·추가·수정·삭제 모두 가능합니다.',
            placement: 'bottom',
        },
        {
            selector: '.toolbar',
            title: '빠른검색 · 필터',
            text: '검색어로 전 컬럼 검색, "완료 포함" · "나만의 태스크" 체크로 빠르게 필터링하세요. 컬럼 헤더 클릭으로 정렬도 됩니다.',
            placement: 'bottom',
        },
        {
            selector: '.grid-wrapper',
            title: '그리드 편집',
            text: '셀 클릭으로 인라인 편집, 세부항목/진행상태는 더블클릭 팝업으로 개행까지 입력 가능. 우클릭으로 행 삽입·복제·삭제 메뉴가 열립니다.',
            placement: 'bottom',
            maxHeight: 200,
        },
    ];

    let currentIdx = 0;
    let activeSteps = [];
    let overlayEl, spotlightEl, tooltipEl;

    function canShowStep(step) {
        const el = document.querySelector(step.selector);
        return el && el.offsetParent !== null; // 숨김 요소 제외 (AI 바 등)
    }

    function ensureDom() {
        if (overlayEl) return;
        overlayEl = document.createElement('div');
        overlayEl.className = 'tour-overlay';
        overlayEl.addEventListener('click', endTour);
        document.body.appendChild(overlayEl);

        spotlightEl = document.createElement('div');
        spotlightEl.className = 'tour-spotlight';
        document.body.appendChild(spotlightEl);

        tooltipEl = document.createElement('div');
        tooltipEl.className = 'tour-tooltip';
        document.body.appendChild(tooltipEl);
    }

    function positionTooltip(rect, placement) {
        const tt = tooltipEl;
        tt.style.maxWidth = '360px';
        const vw = window.innerWidth, vh = window.innerHeight, gap = 12;
        const ttRect = tt.getBoundingClientRect();
        let top, left;
        if (placement === 'top') {
            top = rect.top - ttRect.height - gap;
            left = rect.left + rect.width / 2 - ttRect.width / 2;
            if (top < 8) { top = rect.bottom + gap; }
        } else {
            top = rect.bottom + gap;
            left = rect.left + rect.width / 2 - ttRect.width / 2;
            if (top + ttRect.height > vh - 8) { top = rect.top - ttRect.height - gap; }
        }
        left = Math.max(8, Math.min(left, vw - ttRect.width - 8));
        tt.style.top = top + 'px';
        tt.style.left = left + 'px';
    }

    function renderStep(i) {
        currentIdx = i;
        const step = activeSteps[i];
        const el = document.querySelector(step.selector);
        if (!el) { endTour(); return; }

        el.scrollIntoView({ block: step.maxHeight ? 'start' : 'center', behavior: 'smooth' });

        // 스크롤 안정화를 기다렸다가 좌표 계산
        setTimeout(() => {
            const rect = el.getBoundingClientRect();
            const pad = 6;
            // maxHeight 설정 시 상단부터 해당 높이만 하이라이트 → 툴팁 공간 확보
            const hCap = step.maxHeight ? Math.min(rect.height, step.maxHeight) : rect.height;
            spotlightEl.style.top = (rect.top - pad) + 'px';
            spotlightEl.style.left = (rect.left - pad) + 'px';
            spotlightEl.style.width = (rect.width + pad * 2) + 'px';
            spotlightEl.style.height = (hCap + pad * 2) + 'px';

            const isLast = i === activeSteps.length - 1;
            tooltipEl.innerHTML =
                '<div class="tour-title">' + step.title + '</div>' +
                '<div class="tour-text">' + step.text + '</div>' +
                '<div class="tour-meta">' +
                    '<span class="tour-progress">' + (i + 1) + ' / ' + activeSteps.length + '</span>' +
                    '<div class="tour-buttons">' +
                        '<button class="tour-btn tour-skip" type="button">건너뛰기</button>' +
                        (i > 0 ? '<button class="tour-btn" data-action="prev" type="button">이전</button>' : '') +
                        '<button class="tour-btn tour-btn-primary" data-action="' + (isLast ? 'done' : 'next') + '" type="button">' + (isLast ? '완료' : '다음') + '</button>' +
                    '</div>' +
                '</div>';

            tooltipEl.querySelector('.tour-skip').addEventListener('click', endTour);
            const btns = tooltipEl.querySelectorAll('[data-action]');
            btns.forEach(b => b.addEventListener('click', () => {
                const a = b.dataset.action;
                if (a === 'next') renderStep(i + 1);
                else if (a === 'prev') renderStep(i - 1);
                else if (a === 'done') endTour();
            }));

            // 툴팁 위치는 capped된 하이라이트 기준
            const effectiveRect = { top: rect.top, left: rect.left, width: rect.width, height: hCap, bottom: rect.top + hCap };
            positionTooltip(effectiveRect, step.placement || 'bottom');
        }, 250);
    }

    function startTour(force) {
        if (!force && localStorage.getItem(STORAGE_KEY) === '1') return;
        activeSteps = STEPS.filter(canShowStep);
        if (activeSteps.length === 0) return;
        ensureDom();
        document.body.classList.add('tour-active');
        renderStep(0);
    }

    function endTour() {
        if (!overlayEl) return;
        document.body.classList.remove('tour-active');
        overlayEl.remove(); overlayEl = null;
        spotlightEl.remove(); spotlightEl = null;
        tooltipEl.remove(); tooltipEl = null;
        localStorage.setItem(STORAGE_KEY, '1');
    }

    // ESC로 닫기
    document.addEventListener('keydown', e => {
        if (overlayEl && e.key === 'Escape') endTour();
    });
    // 리사이즈 시 재배치
    window.addEventListener('resize', () => {
        if (overlayEl && activeSteps[currentIdx]) renderStep(currentIdx);
    });

    // 수동 트리거용 전역 함수
    window.startWalkthrough = () => { localStorage.removeItem(STORAGE_KEY); startTour(true); };

    // 자동 시작: 그리드 데이터 로드 후 1.2초 지연
    document.addEventListener('DOMContentLoaded', () => {
        setTimeout(() => startTour(false), 1200);
    });
})();
