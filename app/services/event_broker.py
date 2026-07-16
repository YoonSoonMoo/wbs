"""프로젝트별 실시간 변경 이벤트를 전달하는 인메모리 Pub/Sub 브로커.

SSE(Server-Sent Events) 스트림이 DB 커넥션을 붙잡지 않도록,
변경 발생 시점에 이벤트를 각 구독자의 큐에 넣어주는 방식으로 동작한다.

주의: 단일 프로세스 안에서만 유효하다. 다중 워커/프로세스로 배포하는 경우
      Redis Pub/Sub 등 외부 브로커로 교체해야 워커 간 이벤트가 공유된다.
"""

import queue
import threading

_lock = threading.Lock()
# project_id -> set[queue.Queue]
_subscribers = {}


def subscribe(project_id):
    """프로젝트 이벤트 구독을 시작하고, 이벤트를 받을 큐를 반환한다."""
    q = queue.Queue(maxsize=100)
    with _lock:
        _subscribers.setdefault(project_id, set()).add(q)
    return q


def unsubscribe(project_id, q):
    """구독을 해제한다. (연결 종료 시 반드시 호출)"""
    with _lock:
        subs = _subscribers.get(project_id)
        if subs:
            subs.discard(q)
            if not subs:
                _subscribers.pop(project_id, None)


def publish(project_id, event):
    """해당 프로젝트의 모든 구독자에게 이벤트를 전달한다."""
    with _lock:
        subs = list(_subscribers.get(project_id, ()))
    for q in subs:
        try:
            q.put_nowait(event)
        except queue.Full:
            # 느린 구독자는 이벤트를 드롭한다. 클라이언트는 다음 이벤트나
            # 재연결 시 전체 목록을 다시 불러오므로 최종 상태는 일관된다.
            pass
