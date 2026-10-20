# PR 작성 App 계정 관측 — M84

GitHub Issue의 performed_via_github_app는 이번 PR에서 null이었다. 이 필드를 엄격히 요구하는 기존 writer 관측은 pr_author_app_unavailable로 중단하며, 기대 App ID로 빈 값을 채우지 않는다.

별도 observe_pr_author는 JWT로 인증한 GET /app의 App ID·slug를 시작점으로 삼는다. 운영자 신원으로 저장소/PR/Issue를 조회하고 GET /users/{slug}%5Bbot%5D에서 실제 숫자 봇 ID를 얻어 PR과 Issue 작성자 ID·Bot 타입·login을 모두 대조한다. App 조회를 마지막에 반복해 ID/slug/소유자가 유지되는지도 확인한다. non-null Issue App ID가 다른 App을 가리키면 이 대체 경로에서도 거부한다. 토큰 민팅·쓰기 API는 호출하지 않는다.

GitHub의 [공식 App 토큰 액션 예제](https://github.com/actions/create-github-app-token#configure-git-cli-for-an-apps-bot-user)는 이 봇 사용자 ID 조회 방식을 사용한다. [사용자 조회 API](https://docs.github.com/en/rest/users/users#get-a-user)의 실제 id/type/login과 [Bot 정의](https://docs.github.com/en/graphql/reference/apps#bot)를 함께 대조한다. 여기서 숫자 봇 ID는 App 등록 ID와 다르다.

이는 작성 계정이 해당 App의 봇이라는 별도 관측이다. 원래 null 필드가 채워졌다는 주장이나 과거 POST에 사용된 자격증명의 독립 증명은 아니다. 설치 신원의 PR 파일 조회도 대신하지 않는다. 반환 basis=app_bot_user_lookup과 writer_success_verified=false를 보존하고 기존 writer 성공 입력으로 자동 변환하지 않는다.

실제 결과: App 4924748·봇 328527925·PR #1 작성자 일치, GET 11회, 설치 토큰 발급/쓰기 0회. PR/files/refs 불변 확인. 근거는 docs/evidence/phase5-writer-pr-author-live-2026-09-13.json. 기존 M83 STOPPED/Issue null과 모든 종료 intent는 보존됐다.
