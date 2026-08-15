# Plan — 해커톤 2건 제출: platform-agent를 레퍼런스로 둔 독립 child 2개

작성: 2026-08-15 · 개정: 2026-08-15 (**v3** — parent 무변경 · child 클린룸으로 확정) ·
상태: **계획 (새 레포 없음 · 프로비저닝 없음)**

> 이 문서는 **platform-agent의 작업 계획이 아니다.** 이 레포를 *읽기 전용 레퍼런스*로 두고
> 별도 제출물 2개를 새로 짓는 계획이다. 여기 두는 이유는 §3(추출 목록)과 §8(비용 가드)이
> 이 레포의 자산과 이 레포가 배운 것에 걸리기 때문이다. 추적 권위는 Notion "커리어 실행
> 로드맵", 이 문서는 **기술 실행 계획**만 담는다.

---

## 0. 개정 이력 — 두 번 틀렸고, 왜 틀렸나

| 판 | 구조 | 왜 버렸나 |
|---|---|---|
| v1 | "코드 한 줄도 복사 안 함 · 설계와 교훈만" | **규칙보다 과했다.** 원문이 `frameworks, libraries`를 명시 허용하는데 스스로 족쇄를 채웠다 |
| v2 | parent를 라이브러리로 배포 → child가 의존 | **불필요한 작업을 만들었다.** parent를 공개·패키징·라이선싱해야 했고, 그건 사용자가 원한 것이 아니다 |
| **v3** | **parent 무변경(비공유 레퍼런스) · child는 독립 클린룸** | ← 현재 |

**v3가 옳은 이유**: platform-agent는 **본인을 위한 프로젝트**다. 공유·패키징·라이선싱은
해커톤이 요구하지 않는데 v2가 스스로 만들어 낸 요구였다. 그리고 v3는 **규칙 대응이 가장
깨끗하다**(§2).

## 1. 구조

```
  platform-agent  (비공유 레퍼런스 · 손대지 않는다 · 검증된 설계의 출처)
        ┊
        ┊  읽기만 한다. 임포트하지 않는다. 복사하지 않는다.
        ┊  가져오는 것 = "이 문제는 이렇게 푸는 게 맞더라"는 확인된 설계
        ┊
        ├─────────────────────────────┐
        ▼                             ▼
  child-A (AWS)                 child-B (Google)
  독립 레포 · public + MIT      독립 레포 · private 가능
  Strands Agent + Bedrock       ADK Agent + Gemini 3.5
  "실행됨 ≠ 나아졌음"             "에이전트 함대의 장부"
  마감 2026-09-15 09:00 KST     마감 2026-09-01 09:00 KST
```

**세 가지 성질이 이 구조를 정의한다:**

1. **parent는 변경 0.** 패키징·facade·라이선스·공개 전부 **안 한다.** Phase 4도 무관하다.
2. **child는 자립한다.** parent를 의존성으로 갖지 않는다. 각자 자기 코드만으로 돈다.
3. **child는 실증물이다.** 프로덕션 완성도가 아니라 **4~5분 영상에서 논지가 서는 것**이
   설계 목표다(§6).

## 2. 규칙 대조 — 이 구조가 disclosure를 없앤다

두 대회 Official Rules 원문 확인(2026-08-15). 문언이 **글자 그대로 같다**:

> "Projects must be newly created during the Submission Period."
> "Participants may use standard development tools, including frameworks, libraries,
> starter templates, and AI coding assistants, but must disclose any other
> **pre-existing code or work incorporated into the Project**."

**핵심**: disclosure 의무는 *"incorporated"* — **편입된 것**에 붙는다.

- child가 parent를 **임포트하지도 복사하지도 않으면 편입이 없다** → **신고할 것이 없다.**
- 같은 사람이 같은 문제를 두 번째로 푸는 것은 **경험**이지 pre-existing code가 아니다.
  경험에는 신고 의무가 없다 — 있다면 모든 경력자가 실격이다.

→ **v3는 규칙 대응 부담이 0인 유일한 구조다.** v2는 편입이 있어 신고가 필요했고,
그 신고가 §2의 "비율 위험"을 계속 끌고 다녔다. v3엔 그게 없다.

### ⚠️ 다만 두 가지는 남는다

1. **platform-agent는 현재 GitHub에 public이다**(`men16922/platform-agent`).
   심사위원이 찾을 수 있다. **문제가 되지 않는다** — child가 진짜 새 코드면 유사성은
   같은 저자라는 사실 이상을 뜻하지 않는다. 다만 **비용 0의 보험**으로 child README에
   한 줄을 권한다:

   > Built from scratch during the Submission Period. I maintain a separate personal
   > project (`platform-agent`) in the same problem space; no code from it is used here.

   비공개로 돌리는 것도 방법이지만 **필요하진 않다.** 판단은 본인 몫.

2. ⚠️ **시간에 쫓기면 복사하고 싶어진다.** 이게 v3의 유일한 실무 위험이다.
   **가드**: child를 쓸 때 parent 레포를 같은 에디터에 열지 않는다. 필요한 설계는
   **§3의 추출 목록으로 먼저 글로 옮기고**, 그 글만 보고 짠다.
   (복사하면 그 순간 편입이고, §2의 이점이 통째로 사라진다.)

## 3. 추출 원칙 — 무엇을 뽑고 무엇을 버리나

**뽑는 단위는 "기능"이 아니라 "확인된 설계 판단"이다.** platform-agent가 값진 이유는
코드가 아니라 **틀려 본 기록**이기 때문이다.

### 공통으로 뽑을 것 (설계 판단)

| 판단 | 출처 | child에서의 형태 |
|---|---|---|
| 인시던트를 **정규화 봉투**로 옮기고 provider 세부를 어댑터로 민다 | `NormalizedIncident` | child는 **신호원 1개**만 → 필드 6~8개짜리 dataclass |
| 런북은 **"이 자원엔 안 맞는다"를 선언**할 수 있어야 한다 | M19 `fits_resource` | 런북 2~3개에 `applies_to` 한 필드 |
| 조치는 **AUTO/APPROVE/MANUAL 3단**으로 갈린다 | 승인 게이트 | ⚠️ **축을 바꾼다** — severity가 아니라 **가역성** |
| **선언됐는데 안 읽히는 필드**를 만들지 않는다 | M19·M20 | 필드를 넣을 때 **읽는 쪽을 같이** 짠다 |
| 가드는 **지워 보고 red를 확인**해야 가드다 | Risk 12③ | 테스트 3~5개만, 대신 전부 변이 확인 |

### 버릴 것 (child에 넣지 않는다)

멀티테넌트 스코프 · blast radius · 서명 검증 · 3-cloud 어댑터 · GitOps 렌더 ·
대시보드 · overnight 하네스 · Step Functions · 런북 스토어.

**이유**: 전부 platform-agent를 크게 만든 것들이고, **4분 영상에서 하나도 안 보인다.**
심사 기준 어디에도 "규모"는 없다.

### 크기 목표

| | 목표 | 근거 |
|---|---|---|
| child-A | **≤1,500줄** (테스트 제외) | 주말 2일 + 평일 저녁으로 닫히는 크기 |
| child-B | **≤1,200줄** | 일정이 더 짧다(§7) |

(참고: platform-agent는 추적 소스 **166파일 / 27,562줄**, gate 1912.
⚠️ `find src -name '*.py'`는 4,896을 주는데 `src/stacks/cdk.out`이 섞인 것이다 —
`git ls-files`로 셀 것. `NEXT_PLAN` 유지 규약에 적힌 함정을 이 문서 쓰다 그대로 밟았다.)

## 4. child-A — AWS (주력)

**논지: "실행됨 ≠ 나아졌음"**

대부분의 remediation 에이전트는 액션을 실행하고 **성공을 보고**한다. 실행 성공은
**증상이 사라졌다는 뜻이 아니다.** 이 에이전트는 조치 후 **원래 신호를 스스로 다시 재고**,
안 돌아왔으면 **되돌리거나 에스컬레이션**한다.

- 트랙 **Professional Agents** · 가제 `aftercare`
- 출처: `NEXT_PLAN`의 후속 아티클 소재 ③ — 지어낸 문제가 아니다

**구성 (전부 신규)**

```
  signal      CloudWatch 알람 1종 → 8필드 dataclass
  agent       Strands Agent + tool 4개 (진단 / 조치 / 재측정 / 롤백)
  gate        가역성 축 — 되돌릴 수 있으면 AUTO, 아니면 APPROVE
  verify      ★ 조치 후 N초 대기 → 원신호 재측정 → 회복 판정   ← 논지의 전부
  rollback    재측정 실패 시 자동 역조치
```

| 심사축 (동일 비중) | 획득 경로 |
|---|---|
| Technical Implementation | Strands tool 루프 · Bedrock · 재측정/롤백 |
| Design | 게이트가 **severity가 아니라 가역성**으로 갈린다 |
| Potential Impact | **"온콜의 밤"** — 인프라가 아니라 사람 이야기 |
| Creativity | *"에이전트가 자기 조치를 불신한다"* |
| Presentation | 장애 주입 → 조치 → **재측정 실패 → 롤백** 한 컷 |

**DoD**: 재측정이 **실패하는** 경로가 영상에 있다(성공만 담으면 논지가 안 선다) ·
AWS 실행 증거 · **public repo + MIT** + README + Diagram + ≤5분 YouTube · AWS Builder ID

## 5. child-B — Google (조건부)

**논지: 에이전트 함대의 장부 — 행동에 지출을 귀속한다**

**Fortified Enterprise Fleet** 트랙에 대응하되, 차별점은 **비용을 1급 감사 대상으로 올리는
것**이다. 대부분의 agent observability는 토큰·지연·오류만 보고 **에이전트가 만든 클라우드
지출**은 안 본다.

⚠️ **이 각도는 오늘 실측에서 나왔다**: Phase 4a를 "≈$5/월"로 승인했는데 실제 클러스터를
재니 **≥$180/월**이었다(`docs/evidence/4a-cost-assumed-a-hundredth-of-the-cluster.log`).
**추정이 100배 틀리는 게 정상**이라는 게 출발점이라, 데모가 진짜다.

**구성 (전부 신규)**

```
  registry    에이전트/액션 선언 (Firestore)
  ledger      ★ 액션 1건 → 그 액션이 만든 지출을 귀속해 적는다   ← 논지의 전부
  gate        예산 초과 시 실제로 **막는다** (경보가 아니라 거부)
  agent       ADK Agent + Gemini 3.5 Flash
  runtime     Cloud Run (scale-to-zero)
```

| 심사축 | 비중 | 획득 경로 |
|---|---|---|
| Innovation & Operational Utility | **40%** | 액션 단위 지출 귀속 — 실측에서 나온 문제 |
| Architectural Discipline | 30% | ADK + Gemini 3.5 + Cloud Run + Firestore |
| Demo & Production Readiness | 30% | 4분 영어 + **GCP 실행 시각 증거** + 재현 절차 |

**DoD**: 액션에 지출이 귀속된다 · 예산 초과가 **실제로 거부된다** ·
**Cloud Run에서 도는 시각 증거** · Diagram · ≤4분 **영어** 영상

## 6. 실증 최적화 — child의 아키텍처는 데모가 결정한다

**이게 v3에서 새로 들어간 절이고, "실증 용도"라는 요구의 직접 번역이다.**

프로덕션 코드와 실증 코드는 **다른 것을 최적화한다.** child는 후자다:

1. **결정론적 데모.** 장애 주입은 `make demo` 한 줄로 재현된다. 랜덤·외부 의존 금지.
2. **타이머를 줄인다.** platform-agent의 데모 룰이 `for: 1m`인 이유와 같다
   (stock `KubePodCrashLooping`은 15분이라 영상에 못 담는다). child의 재측정 대기·
   예산 창은 **영상 길이에 맞춘 값**이어야 한다 — 그리고 **그 값을 상수 한 곳에** 둔다.
3. **실패 경로를 1급으로 만든다.** 두 child 모두 DoD에 넣었다. 성공만 담은 데모는
   *"그래서 안 될 땐?"* 한 줄에 무너진다.
4. **화면에 보이게 만든다.** 내부 상태(판정 근거·귀속된 금액)가 로그가 아니라
   **출력**으로 나와야 4분 안에 전달된다.
5. ⚠️ **그렇다고 가짜로 만들지 않는다.** 타이머를 줄이는 건 최적화지만 결과를 하드코딩하면
   실증이 아니다. platform-agent가 M18에서 배운 것 — **기본값과 같은 값을 고른 픽스처는
   가드가 아니다**.

## 7. 두 대회 요건 (원문 확인 완료)

| | **AWS Agents for Humans** | **Google All Things Agentic** |
|---|---|---|
| Submission Period | **08-10 ~ 09-14 17:00 PT** | 08-03 ~ 08-31 17:00 PT |
| 한국 마감 | **2026-09-15 09:00 KST** | **2026-09-01 09:00 KST** |
| 남은 일수(08-15) | **31일** | **17일** |
| 필수 프레임워크 | **Strands Agents SDK** | ADK / GenAI SDK / Antigravity / GenKit 중 1 |
| 필수 모델 | (Bedrock 전제) | **Gemini 3.5 이상** |
| 필수 인프라 | AWS 실행 증거 | **Google Cloud 1종 이상** |
| 레포 | **public 필수 + MIT/Apache 파일 필수** | **private 허용** · 라이선스 요건 **없음** |
| 영상 | ≤5분 공개 YouTube/Vimeo | **≤4분 영어** + GCP 배포 시각 증거 |
| 심사 | 5축 **동일 비중** | Innovation 40% · Architecture 30% · Demo 30% |
| 크레딧 | $50 — **09-11 12:00 PT** | $150 — **08-28 12:00 PT** |

⚠️ **Notion의 AWS "시작일 08-31"은 요강이 아니라 본인 스프린트 계획**이다.
실제 기간은 **08-10에 열렸다**.

## 8. 순서 — 마감이 이른 쪽부터

| | 마감 (KST) | 남은 일수(08-15) | 순서 |
|---|---|---|---|
| **child-B** (Google) | **09-01 09:00** | **17일** | **먼저** |
| **child-A** (AWS) | 09-15 09:00 | 31일 | 나중 |

**B를 먼저 하는 이유는 마감이 2주 이르기 때문이고, 그게 전부다.** 두 child는 코드를
공유하지 않으므로(§11) 순서에 기술적 의존은 없다.

**크레딧 마감이 각 child의 실제 착수 하한**이다: Google **08-28 12:00 PT** ·
AWS 09-11 12:00 PT. 크레딧 없이 시작하면 §9-1을 어기게 된다.

### ⚠️ child-B 중단 기준 (kill criteria)

**Cloud Run에서 도는 것이 없는 상태로 08-24를 넘기면 child-B를 버린다.**

근거는 남은 일정 산수다 — 08-31 제출을 맞추려면 마지막 주에 **ledger + gate + 4분 영어
영상 + README + Diagram**이 남아야 하고, 그 앞의 "배포가 된다"는 그때까지 이미 참이어야
한다. 배포는 child-B DoD에서 **가장 먼저 참이 될 수 있는 항목**이라, 이게 안 되면 뒤가
전부 밀린다.

**포기 비용은 0이다**(제출 안 하면 그만). 하나만 남기면 **child-A**다 — 마감이 2주 더
있고, 필수 스택(Strands)이 이미 익숙하며, public+MIT 외에 별도 요건이 없다.

## 9. 비용 — 오늘 배운 것을 그대로 적용

**오늘 4a 실측 교훈**: 추정의 *가정*이 총액을 지배하고, 그 가정은 안심시키는 쪽으로 틀린다.
해커톤 인프라는 **7월 GKE 방치와 같은 모양**(잊힌 컴퓨트)이라 선제로 막는다.

| child | 쓸 것 | 금지 | 근거 |
|---|---|---|---|
| B (Google) | **Cloud Run**(scale-to-zero) + Vertex Gemini 3.5 Flash + Firestore | ⛔ **GKE** | Cloud Run은 유휴 시 0으로 수렴 · GKE는 상시 과금 = 7월 사건 경로 |
| A (AWS) | Lambda + Bedrock on-demand · (선택) AgentCore | ⛔ **EKS** · ⛔ 상시 EC2 | 08-09 t3.medium 18일 방치 $8.03 전례 |

**강제 규칙 (요건이 아니라 자기 가드):**

1. **크레딧을 먼저 받는다** — 못 받으면 범위를 줄이지, 자비로 메우지 않는다.
2. **teardown 날짜를 제출과 동시에 박는다** — B: 09-02 · A: 09-16.
   심사 중 Hosted가 필요하면 **scale-to-zero만** 남긴다.
3. **`make spend-check`는 주 2회** — CE는 요청당 $0.01이고 08-09~12엔 **그날의 최대 지출
   항목**이었다(점검이 대상보다 더 썼다).
4. ⚠️ **GCP는 아직 지출을 못 읽는다**(BQ 내보내기 미완 → Risk 4).
   **child-B를 하면 BQ 내보내기가 선택이 아니라 선행 조건**이다.
   ⚠️ 아이러니: child-B의 논지가 "비용 감사"인데 **그 클라우드의 비용을 못 읽는 상태**다.
   → **데모 소재로 뒤집을 수 있다** — "무엇이 안 보이는지"가 그 논지의 출발점이다.

## 10. 선행 차단 요소 — v2보다 대폭 줄었다

- [ ] **① AWS Builder ID 발급** — child-A 제출 필수물.
- [ ] **② 크레딧 2건** — Google **08-28 12:00 PT** · AWS 09-11 12:00 PT.
- [ ] **③ child 레포 2개 생성** — 착수 시점에. child-A는 **public + MIT**로 시작한다
      (나중에 붙이면 커밋 이력이 어색해진다).
- [x] ~~parent LICENSE / facade / 패키징~~ → **v3에서 불필요.** parent는 손대지 않는다.
- [x] ~~Google Official Rules 원문 확인~~ → **완료(08-15)**. Notion 요약과 일치했고
      **레포 요건 차이 하나**가 추가로 나왔다(Google은 private 허용·라이선스 불요).

⚠️ **별건이지만 남아 있다**: 워킹트리에 `docs/generate_architecture.py`·`JOURNEY.md` 삭제가
커밋 안 된 채 떠 있다. **Diagram 생성 수단**이고 `JOURNEY.md`는
`docs/plans/2026-07-20-onprem-platform-addons.md`가 7곳에서 참조한다. **이 계획과 무관하게**
의도 확인이 필요하다.

## 11. 이 계획이 하지 않는 것

- **platform-agent를 건드리지 않는다.** 라이선스·패키징·공개·기능 전부 **안 한다.**
- **새 레포를 만들지 않았다.** 이름(`aftercare`/`fleet-ledger`)은 **제안**이다.
- **아무것도 프로비저닝하지 않았다.**
- **Phase 4와 독립이다.**
- **두 child 사이에 코드를 공유하지 않는다.** 중복이 생기지만, 각자 ≤1,500줄이고
  모노스택이 요구되며 **공유 층을 만들면 v2의 문제가 되돌아온다.**

## 12. 리스크 — 정직하게

1. **⚠️ 복사 유혹이 유일한 실질 위험이다(§2-2).** 시간에 쫓기면 parent에서 긁어오게 된다.
   그 순간 편입이 생기고 v3의 이점이 통째로 사라진다. 가드는 §2에 적은 **"parent를 같은
   에디터에 열지 않는다"** 하나뿐이고, 이건 기술이 아니라 규율이다.
2. **child-B의 17일이 진짜 제약이다.** 4분 **영어** 영상까지 포함해서다. §8 중단 기준이
   유일한 관리 수단이고, 그건 일정 관리가 아니라 **손실 확정 장치**다.
3. **단가를 안 쟀다.** §9는 "유휴 시 0으로 수렴"이라는 **성질**에 근거하지 **측정**이
   아니다 — AgentCore·Cloud Run 실단가 미측정. **오늘 4a에서 틀린 것이 정확히 이 종류다.**
4. **영상이 병목이다.** 4분 **영어** 영상(Google)은 코드보다 오래 걸릴 수 있다.
5. **≤1,500줄 목표가 낙관일 수 있다.** child-A의 verify 루프는 *"신호가 회복됐는가"*를
   판정해야 하는데, 그 판정 자체가 platform-agent에서 아직 안 푼 문제다
   (`NEXT_PLAN`: `resolved_at`을 읽는 쪽이 AWS뿐). **child에서 처음 푸는 것**이라
   시간이 더 걸릴 수 있고 — 뒤집으면 **그래서 제출할 가치가 있다.**

---

**다음 행동**: §10의 ①(Builder ID)·②(크레딧). 08-16 착수 전까지 끝나면 된다.
