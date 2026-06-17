---
name: push-gitea
description: 깃티아(Gitea) 미러 저장소에 현재 브랜치를 푸시한다. 사용자가 "깃티아에 푸시해줘", "gitea에도 올려줘", "gitea push" 등으로 명시적으로 요청할 때만 사용한다.
---

# 깃티아 푸시 (미러)

이 프로젝트는 두 곳의 원격 저장소를 사용한다.

| remote | URL | 용도 |
|--------|-----|------|
| `origin` | https://github.com/YoonSoonMoo/wbs.git | 기본 (push/fetch/pull) |
| `gitea`  | https://gitea.daou.co.kr/yoonsm/wbs.git | **미러 전용 (명시 요청 시 push만)** |

## 원칙

- 일반적인 "푸시해줘"는 **`origin`에만** 푸시한다. (이 스킬을 쓰지 않음)
- fetch / pull 은 **항상 `origin`에서만** 가져온다. 깃티아는 가져오지 않는다.
- **"깃티아에 푸시해줘"** 류의 명시적 요청이 있을 때만 이 스킬로 `gitea`에 푸시한다.

## 실행 순서

1. **remote 확인** — `gitea` remote가 없으면 추가한다.
   ```bash
   git remote get-url gitea 2>/dev/null || git remote add gitea https://gitea.daou.co.kr/yoonsm/wbs.git
   ```

2. **현재 브랜치를 gitea에 푸시**
   ```bash
   git push gitea HEAD
   ```
   - 미러 최초 동기화 시, 깃티아 저장소가 자동 초기 커밋(README 등)을 가진 채로 생성되어 `[rejected] (fetch first)`가 날 수 있다. 이때는 로컬 히스토리로 덮어쓴다: `git push gitea HEAD --force` (origin/로컬에는 영향 없음). 최초 1회 이후엔 `--force` 불필요.

## 주의사항

- 깃티아 인증 정보가 없어 푸시가 실패하면(`Authentication failed` 등), 사용자에게 `! git push gitea HEAD` 를 직접 실행하도록 안내한다. (자격 증명 입력이 필요할 수 있음)
- 푸시 결과(성공/실패, 푸시된 커밋 범위)를 그대로 보고한다. 실패를 숨기지 않는다.
