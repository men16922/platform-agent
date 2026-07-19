# LinkedIn cut — short-form posts

Short posts derived from the long-form architecture article
(`platform-agent-architecture.md` / `-ko.md`). Pick one, tweak the CTA/link, publish.

---

## English (≈4 short paragraphs)

I built a platform-operations agent that provisions clusters, ships deployments, and remediates incidents by itself — across AWS, GCP, Azure, and fully offline on-prem. One plain-English sentence ("provision an on-prem cluster, then deploy orders-api and confirm it's healthy") becomes a planned, traced, approval-gated sequence of real infrastructure actions.

The hard part was never "can an LLM call tools." It was: how do you keep it from acting on a hallucination, and how do you make the irreversible actions safe? So most of the engineering went into guardrails, not autonomy:

• A reconciliation gate that refuses to auto-act on a root cause the model can't ground in real tool output — proven live: a grounded LLM analysis stayed AUTO, a hallucinated guess got downgraded to human approval.
• Self-consistency voting on routing, with a deterministic fallback when the model self-disagrees.
• A remote-MCP connector with a per-tool + global kill-switch, and cross-account STS with graceful in-account fallback — both demonstrated over real HTTP and real STS.

The lesson: the headline feature of an agentic tool is autonomy, but the shippable feature is trust. LLMs propose; verified, deterministic logic disposes. 854 tests, live end-to-end on three real clouds.

Full write-up 👇 [link]

#AIAgents #PlatformEngineering #Kubernetes #LLM #SRE #DevOps

---

## 한국어 (≈4 단락)

클러스터를 프로비저닝하고, 배포를 내보내고, 장애를 스스로 복구하는 플랫폼 운영 에이전트를 만들었습니다 — AWS·GCP·Azure, 그리고 완전 오프라인 온프렘까지. 자연어 한 문장("온프렘 클러스터를 만들고 orders-api를 배포한 뒤 정상인지 확인해줘")이 계획되고, 추적되며, 승인 게이트를 거치는 실제 인프라 작업으로 바뀝니다.

어려운 건 "LLM이 도구를 호출할 수 있나"가 아니었습니다. **환각 위에서 행동하지 않게 어떻게 막고, 되돌릴 수 없는 작업을 어떻게 안전하게 만드는가**였죠. 그래서 엔지니어링의 대부분은 자율성이 아니라 가드레일에 들어갔습니다:

• 모델이 실제 도구 결과로 뒷받침하지 못하는 근본 원인 위에서 자동 실행하기를 거부하는 **정합성 게이트** — 라이브 실증: 증거에 근거한 LLM 분석은 AUTO 유지, 증거 없이 추측한 분석은 사람 승인으로 강등.
• 라우팅에 대한 **자기일관성 투표**, 모델이 자기모순일 땐 결정론적 폴백.
• 도구별·전역 **kill-switch**를 가진 원격 MCP 커넥터, 그리고 우아한 in-account 폴백을 갖춘 **크로스계정 STS** — 둘 다 실제 HTTP·실제 STS로 실증.

교훈은 이렇습니다. 에이전틱 도구의 표제 기능은 자율성이지만, **출시 가능한 기능은 신뢰**입니다. LLM은 제안하고, 검증된 결정론적 로직이 처분합니다. 테스트 854개, 세 개의 실제 클라우드에서 라이브 E2E.

전체 글은 👇 [링크]

#AI에이전트 #플랫폼엔지니어링 #Kubernetes #LLM #SRE #DevOps
